from __future__ import annotations

"""
generative/rag/vectorstore.py
================================
FAISS-based vector store for AgriSense agronomic knowledge base.
Provides semantic retrieval for crop-specific advisory context.
"""

import logging
import os
import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# Optional FAISS import — graceful fallback if not installed
try:
    import faiss  # type: ignore
    _FAISS_AVAILABLE = True
except ImportError:
    _FAISS_AVAILABLE = False
    log.warning("faiss-cpu not installed. VectorStore will use cosine similarity fallback.")

# Optional sentence-transformers for embedding
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False
    log.warning("sentence-transformers not installed. Using simple TF-IDF fallback embeddings.")


DEFAULT_INDEX_PATH = "configs/agri_faiss.index"
DEFAULT_DOCS_PATH = "configs/agri_docs.pkl"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # lightweight, multilingual-capable


class AgriVectorStore:
    """
    FAISS-backed vector store for agricultural knowledge retrieval.
    Falls back to NumPy cosine similarity if FAISS is not installed.
    """

    def __init__(
        self,
        index_path: str = DEFAULT_INDEX_PATH,
        docs_path: str = DEFAULT_DOCS_PATH,
        embedding_dim: int = 384,
    ) -> None:
        self.index_path = index_path
        self.docs_path = docs_path
        self.embedding_dim = embedding_dim
        self.documents: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index: Any = None  # type: ignore
        self._embedder: Any = None

        # Try to load persisted index
        if Path(index_path).exists() and Path(docs_path).exists():
            self._load()

    def _get_embedder(self) -> Any:
        """Lazy-loads the sentence embedding model."""
        if self._embedder is None:
            if _ST_AVAILABLE:
                self._embedder = SentenceTransformer(EMBEDDING_MODEL)
                log.info("Loaded SentenceTransformer: %s", EMBEDDING_MODEL)
            else:
                self._embedder = None
        return self._embedder

    def _embed(self, texts: List[str]) -> np.ndarray:
        """Embeds a list of texts into float32 numpy array."""
        embedder = self._get_embedder()
        if embedder is not None:
            vecs = embedder.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
            return vecs.astype(np.float32)
        else:
            # Fallback: simple character-level bag-of-words (for testing without GPU)
            from sklearn.feature_extraction.text import TfidfVectorizer
            if not hasattr(self, "_tfidf"):
                self._tfidf = TfidfVectorizer(max_features=self.embedding_dim)
                vecs = self._tfidf.fit_transform(texts).toarray().astype(np.float32)
            else:
                vecs = self._tfidf.transform(texts).toarray().astype(np.float32)
            # L2 normalize
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            return vecs / norms

    def add_documents(self, documents: List[str]) -> None:
        """Indexes a list of text documents."""
        if not documents:
            log.warning("No documents provided to index.")
            return

        log.info("Indexing %d documents...", len(documents))
        self.documents.extend(documents)
        new_vecs = self._embed(documents)

        if _FAISS_AVAILABLE:
            if self.index is None:
                self.index = faiss.IndexFlatIP(new_vecs.shape[1])  # inner product (cosine for normalized)
            self.index.add(new_vecs)
        else:
            # Store as numpy matrix for cosine fallback
            if self.embeddings is None:
                self.embeddings = new_vecs
            else:
                self.embeddings = np.vstack([self.embeddings, new_vecs])

        self._save()
        log.info("Indexed %d documents. Total: %d", len(documents), len(self.documents))

    def search(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        Retrieves the top_k most relevant documents for a query.

        Returns
        -------
        List of (document_text, similarity_score) tuples
        """
        if not self.documents:
            log.warning("VectorStore is empty. No documents to retrieve.")
            return []

        query_vec = self._embed([query])

        if _FAISS_AVAILABLE and self.index is not None:
            scores, indices = self.index.search(query_vec, min(top_k, len(self.documents)))
            results = [(self.documents[i], float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]
        elif self.embeddings is not None:
            # NumPy cosine similarity fallback
            sims = (self.embeddings @ query_vec.T).squeeze()
            top_idx = np.argsort(sims)[::-1][:top_k]
            results = [(self.documents[i], float(sims[i])) for i in top_idx]
        else:
            return []

        log.info("Retrieved %d docs for query: '%s...'", len(results), query[:50])
        return results

    def _save(self) -> None:
        """Persists the index and documents to disk."""
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        with open(self.docs_path, "wb") as f:
            pickle.dump(self.documents, f)
        if _FAISS_AVAILABLE and self.index is not None:
            faiss.write_index(self.index, self.index_path)
        elif self.embeddings is not None:
            np.save(self.index_path + ".npy", self.embeddings)
        log.info("VectorStore saved to %s", self.index_path)

    def _load(self) -> None:
        """Loads the persisted index and documents."""
        try:
            with open(self.docs_path, "rb") as f:
                self.documents = pickle.load(f)
            if _FAISS_AVAILABLE and Path(self.index_path).exists():
                self.index = faiss.read_index(self.index_path)
            elif Path(self.index_path + ".npy").exists():
                self.embeddings = np.load(self.index_path + ".npy")
            log.info("VectorStore loaded: %d documents", len(self.documents))
        except Exception as exc:
            log.error("Failed to load VectorStore: %s. Starting fresh.", exc)
            self.documents = []
            self.index = None
            self.embeddings = None


# Module-level singleton
_store: Optional[AgriVectorStore] = None

def get_vector_store() -> AgriVectorStore:
    """Returns the module-level AgriVectorStore singleton."""
    global _store
    if _store is None:
        _store = AgriVectorStore()
    return _store


def seed_knowledge_base(store: Optional[AgriVectorStore] = None) -> None:
    """
    Seeds the vector store with core agronomic knowledge documents.
    Run once on first deployment to bootstrap the knowledge base.
    """
    vs = store or get_vector_store()
    docs = [
        # Irrigation
        "Wheat requires 450-650mm of water throughout its growth cycle. "
        "Irrigate at crown root initiation (21 DAS), tillering (40 DAS), "
        "jointing (60 DAS), flowering (90 DAS), and grain filling (100 DAS).",

        "Rice (paddy) needs standing water of 5-7cm during most growth stages. "
        "Reduce water 10 days before harvest to facilitate ripening. "
        "Total water requirement is 1200-2000mm per season.",

        "Drip irrigation can reduce water use by 30-50% compared to flood irrigation "
        "for crops like tomato, sugarcane, and cotton. Install emitters at 50-60cm spacing.",

        # Soil & Nutrients
        "Soil moisture below 30% of field capacity indicates water stress in most crops. "
        "Field capacity for clay soils: 35-45%, loam: 25-35%, sandy: 10-15%.",

        "Nitrogen deficiency appears as yellowing of older leaves (chlorosis) starting "
        "from leaf tips. Apply urea at 46% N concentration. Wheat requires 120-150 kg N/ha.",

        "Potassium deficiency causes brown scorching of leaf margins. "
        "Apply muriate of potash (KCl, 60% K2O) at 60-80 kg K2O/ha for most cereals.",

        # Pest & Disease
        "Brown planthopper (BPH) in rice causes 'hopperburn' — circular yellowing patches. "
        "Spray imidacloprid 17.8% SL at 100ml/ha. Avoid water shortage which increases BPH.",

        "Wheat rust (yellow rust, brown rust) spreads in cool humid conditions. "
        "Apply propiconazole 25% EC at 500ml/ha at first sign. Resistant varieties preferred.",

        "Fall armyworm (FAW) in maize shows characteristic 'window pane' feeding. "
        "Apply chlorantraniliprole 18.5 SC at 0.4ml/L water. Early morning application preferred.",

        # Yield & Seasons
        "Kharif crops (June-October): Rice, maize, soybean, cotton, groundnut. "
        "Rabi crops (November-March): Wheat, barley, mustard, chickpea, lentil. "
        "Zaid crops (April-June): Cucumber, watermelon, bitter gourd, muskmelon.",

        "Average wheat yield in India: 3.2-3.5 t/ha. Punjab highest at 4.5 t/ha. "
        "Target 5+ t/ha with improved varieties like HD-2967 and DBW-187.",

        # Weather & Climate
        "Growing Degree Days (GDD) = max(0, (T_max + T_min)/2 - T_base). "
        "T_base for wheat = 0°C, maize = 10°C, rice = 10°C. "
        "Wheat flowering at GDD ~1200, maturity at ~2200.",

        "Evapotranspiration (ET) calculation using Hargreaves method: "
        "ET = 0.0023 * Ra * (T_mean + 17.8) * (T_max - T_min)^0.5. "
        "Ra = extraterrestrial radiation (MJ/m2/day).",
    ]
    vs.add_documents(docs)
    log.info("Knowledge base seeded with %d agricultural documents.", len(docs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    store = AgriVectorStore(index_path="configs/test_faiss.index", docs_path="configs/test_docs.pkl")
    seed_knowledge_base(store)
    results = store.search("When to irrigate wheat?", top_k=2)
    for doc, score in results:
        print(f"Score={score:.3f} | {doc[:100]}...")
