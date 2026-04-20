"""
nodes/historical_db_node.py — LangGraph node that populates HistoricalContext.

Design notes:
- The node is a plain async-compatible function (not a class) so LangGraph can
  call it directly without wrapping.
- All DB and feature-extraction errors are caught and logged; the node sets the
  HistoricalContext to a degraded (all-None) state and records the error in
  AgriState.errors so the pipeline can continue with partial data.
- pest_risk_score formula:
    Σ(severity_i × affected_area_pct_i) / (N × 5 × 100)
  where N = number of pest records in the last 3 seasons, 5 = max severity,
  100 = max affected_area_pct → score ∈ [0, 1].
- The node does NOT commit any writes; it is strictly a read + transform node.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


def historical_db_node(state: Any) -> Any:
    """
    LangGraph node: fetch and derive historical features for state.farm_id.

    Parameters
    ----------
    state : AgriState
        The shared pipeline state object. Must have a ``farm_id`` field.

    Returns
    -------
    AgriState
        The same state object with ``historical`` field populated.
    """
    from historical_db.db_connector import HistoricalDBConnector
    from preprocessing.historical_feature_extractor import HistoricalFeatureExtractor
    from state import HistoricalContext

    farm_id: str = getattr(state, "farm_id", "") if not isinstance(state, dict) else state.get("farm_id", "")
    logger.info("historical_db_node started for farm_id=%s", farm_id)

    if not farm_id:
        logger.error("historical_db_node received empty farm_id — aborting node.")
        if isinstance(state, dict):
            state["errors"] = state.get("errors", []) + ["historical_db_node: Empty farm_id provided."]
            state["historical"] = _degraded_context(farm_id)
        else:
            state.add_error("historical_db_node", "Empty farm_id provided.")
            state.historical = _degraded_context(farm_id)
        return state

    try:
        db = HistoricalDBConnector()
        db.open()
    except EnvironmentError as exc:
        logger.warning(
            "historical_db_node: DB env vars missing (%s) — degraded mode.", exc
        )
        state.add_error("historical_db_node", f"DB env vars missing: {exc}")
        state.historical = _degraded_context(farm_id)
        return state
    except Exception as exc:
        logger.warning(
            "historical_db_node: cannot connect to DB (%s) — degraded mode.", exc
        )
        state.add_error("historical_db_node", f"DB connection failed: {exc}")
        state.historical = _degraded_context(farm_id)
        return state

    try:
        extractor = HistoricalFeatureExtractor(db)
        features = extractor.extract_all(farm_id)

        yield_history = _yield_history_list(db, farm_id)
        pest_risk = _compute_pest_risk(db, farm_id)
        llm_summary = features.get("llm_summary", {})
        soil_deficiencies = llm_summary.get("soil_deficiencies", [])
        irr_efficiency = llm_summary.get("irrigation_efficiency")

        if isinstance(state, dict):
            state["historical"] = HistoricalContext(
                farm_id=farm_id,
                yield_history=yield_history,
                pest_risk_score=pest_risk,
                soil_deficiencies=soil_deficiencies,
                irrigation_efficiency=irr_efficiency,
                farm_summary=llm_summary,
                last_updated=datetime.utcnow(),
            )
        else:
            state.historical = HistoricalContext(
                farm_id=farm_id,
                yield_history=yield_history,
                pest_risk_score=pest_risk,
                soil_deficiencies=soil_deficiencies,
                irrigation_efficiency=irr_efficiency,
                farm_summary=llm_summary,
                last_updated=datetime.utcnow(),
            )
        logger.info(
            "historical_db_node completed — pest_risk=%.3f deficiencies=%s",
            pest_risk or 0.0,
            soil_deficiencies,
        )

    except Exception as exc:
        logger.warning(
            "historical_db_node: feature extraction failed (%s) — degraded mode.", exc
        )
        if isinstance(state, dict):
            state["errors"] = state.get("errors", []) + [f"historical_db_node: Feature extraction failed: {exc}"]
            state["historical"] = _degraded_context(farm_id)
        else:
            state.add_error("historical_db_node", f"Feature extraction failed: {exc}")
            state.historical = _degraded_context(farm_id)
    finally:
        db.close()

    return state


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------
def _yield_history_list(db: Any, farm_id: str) -> list[dict]:
    """Return yield history as a list of dicts for all crops, last 5 years."""
    from sqlalchemy import text

    sql = text(
        """
        SELECT
            yr.record_id, yr.farm_id, yr.crop_id, c.crop_name,
            yr.season, yr.year, yr.yield_kg_per_hectare, yr.harvest_date, yr.notes
        FROM yield_records yr
        JOIN crops c ON c.crop_id = yr.crop_id
        WHERE yr.farm_id = :farm_id
          AND yr.year   >= (CAST(strftime('%Y', 'now') AS INTEGER) - 5)
        ORDER BY yr.harvest_date
        """
    )
    try:
        with db._get_session() as session:
            result = session.execute(sql, {"farm_id": farm_id})
            rows = result.fetchall()
            keys = result.keys()
            records = []
            for row in rows:
                d = dict(zip(keys, row))
                # JSON-safe conversion
                for k, v in d.items():
                    if hasattr(v, "isoformat"):
                        d[k] = v.isoformat()
                    elif hasattr(v, "__str__") and "UUID" in type(v).__name__:
                        d[k] = str(v)
                records.append(d)
            return records
    except Exception as exc:
        logger.warning("_yield_history_list failed: %s", exc)
        return []


def _compute_pest_risk(db: Any, farm_id: str) -> float | None:
    """
    Compute normalised pest risk score over last 3 seasons.

    score = Σ(severity_i × affected_area_pct_i) / (N × 5 × 100)
    Returns None if no pest records found.
    """
    three_years_ago = date.today() - timedelta(days=3 * 365)
    try:
        pest_df = db.get_pest_history(farm_id, three_years_ago, date.today())
    except Exception as exc:
        logger.warning("_compute_pest_risk: DB query failed: %s", exc)
        return None

    if pest_df.empty:
        return None

    pest_reset = pest_df.reset_index()
    n = len(pest_reset)
    if n == 0:
        return None

    weighted_sum = float(
        (pest_reset["severity"] * pest_reset["affected_area_pct"]).sum()
    )
    max_possible = n * 5.0 * 100.0
    score = round(weighted_sum / max_possible, 4)
    return min(1.0, max(0.0, score))


def _degraded_context(farm_id: str) -> Any:
    """Return a HistoricalContext with all fields set to empty/None for degraded mode."""
    from state import HistoricalContext

    return HistoricalContext(
        farm_id=farm_id,
        yield_history=[],
        pest_risk_score=None,
        soil_deficiencies=[],
        irrigation_efficiency=None,
        farm_summary={},
        last_updated=datetime.utcnow(),
    )


if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    # Simulate a minimal state object
    import uuid as _uuid

    class MockState:
        farm_id = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "farm_punjab_amarinder"))
        historical = None
        errors: list[str] = []
        satellite = None
        iot_sensors = None
        weather = None
        farmer_sms = None

        def add_error(self, source: str, message: str) -> None:
            self.errors.append(f"[{source}] {message}")

    result_state = historical_db_node(MockState())
    if result_state.historical:
        import json
        print(json.dumps(result_state.historical.to_dict(), indent=2, default=str))
    else:
        print("Degraded — no historical context produced.")
