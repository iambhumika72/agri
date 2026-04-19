from __future__ import annotations

import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

# Support both SDK versions
try:
    from google import genai
    from google.genai import types as genai_types
    _USE_NEW_SDK = True
except ImportError:
    import google.generativeai as genai  # type: ignore
    genai_types = genai.types  # type: ignore
    _USE_NEW_SDK = False


class GeminiClient:
    """
    Unified wrapper for the Gemini API supporting both the modern
    google.genai SDK and the legacy google.generativeai SDK.
    Falls back gracefully if the API key is missing.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash") -> None:
        self.model_name = model_name
        self._client: Any = None
        self._initialized = False

    def _initialize(self) -> None:
        """Lazy initialization — only connects when first called."""
        if self._initialized:
            return
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. "
                "Get a key at https://aistudio.google.com/app/apikey"
            )
        if _USE_NEW_SDK:
            self._client = genai.Client(api_key=api_key)
            log.info("GeminiClient initialized with google.genai SDK (model=%s)", self.model_name)
        else:
            genai.configure(api_key=api_key)
            self._client = genai.GenerativeModel(model_name="gemini-1.5-pro")
            log.info("GeminiClient initialized with legacy SDK (model=gemini-1.5-pro)")
        self._initialized = True

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> str:
        """
        Sends a text prompt and returns the raw response string.

        Parameters
        ----------
        prompt : str — the user prompt
        system_instruction : str | None — system role instruction
        temperature : float — generation temperature (0.0 = deterministic)
        max_tokens : int — max output tokens

        Returns
        -------
        str — the model's text response
        """
        self._initialize()
        contents = []
        if system_instruction:
            contents.append(system_instruction)
        contents.append(prompt)

        if _USE_NEW_SDK:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
        else:
            response = self._client.generate_content(
                contents,
                generation_config=genai_types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )

        return response.text

    def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> str:
        """
        Wrapper for structured (JSON) generation with near-zero temperature.
        Returns raw text; caller is responsible for JSON parsing.
        """
        return self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_tokens=1024,
        )


# Module-level singleton
_client_instance: Optional[GeminiClient] = None

def get_gemini_client(model_name: str = "gemini-2.0-flash") -> GeminiClient:
    """Returns the module-level singleton GeminiClient."""
    global _client_instance
    if _client_instance is None:
        _client_instance = GeminiClient(model_name=model_name)
    return _client_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    client = get_gemini_client()
    # Requires GEMINI_API_KEY in environment
    try:
        response = client.generate("Say hello to an Indian farmer in one sentence.")
        print(f"Response: {response}")
    except EnvironmentError as e:
        print(f"No API key found: {e}")
