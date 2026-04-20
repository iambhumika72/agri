"""
ingestion/mandi_price_ingestion.py
====================================
Mandi Price Ingestion Module for the Trace Agricultural AI System.
Fetches historical commodity prices from the Agmarknet API (data.gov.in).

API Endpoint: https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from historical_db.db_connector import HistoricalDBConnector

log = logging.getLogger(__name__)

AGMARKNET_API_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
API_KEY = os.environ.get("AGMARKNET_API_KEY")


class MandiPriceIngester:
    """Async ingester for Agmarknet commodity prices."""

    def __init__(self, api_key: Optional[str] = API_KEY) -> None:
        self.api_key = api_key
        if not self.api_key:
            log.warning("AGMARKNET_API_KEY not set. API requests will fail if public access is restricted.")

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def fetch_prices(
        self,
        state: Optional[str] = None,
        district: Optional[str] = None,
        commodity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Fetch records from Agmarknet API with filtering and pagination.
        """
        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": limit,
            "offset": offset,
        }

        # Add filters if provided
        if state:
            params["filters[state]"] = state
        if district:
            params["filters[district]"] = district
        if commodity:
            params["filters[commodity]"] = commodity

        log.info(
            "Fetching mandi prices | state=%s district=%s commodity=%s limit=%d offset=%d",
            state, district, commodity, limit, offset
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(AGMARKNET_API_URL, params=params)
            resp.raise_for_status()
            return resp.json()

    def _persist_records(self, records: list[dict[str, Any]]) -> int:
        """
        Sync helper to persist records using the HistoricalDBConnector.
        This follows the existing pattern in db_connector.py.
        """
        count = 0
        with HistoricalDBConnector() as db:
            for rec in records:
                try:
                    # Clean and parse fields
                    # API dates are typically DD/MM/YYYY
                    arrival_date_str = rec.get("arrival_date", "")
                    try:
                        arrival_date = datetime.strptime(arrival_date_str, "%d/%m/%Y").date()
                    except ValueError:
                        # Fallback for ISO format if API evolves
                        arrival_date = datetime.fromisoformat(arrival_date_str).date()

                    price_data = {
                        "state": rec["state"],
                        "district": rec["district"],
                        "market": rec["market"],
                        "commodity": rec["commodity"],
                        "variety": rec["variety"],
                        "arrival_date": arrival_date,
                        "min_price": float(rec.get("min_price", 0)),
                        "max_price": float(rec.get("max_price", 0)),
                        "modal_price": float(rec.get("modal_price", 0)),
                    }
                    
                    # We check for allowed tables in insert_record
                    # Since mandi_prices is new, we need to ensure it's in the allowed set.
                    db.insert_record("mandi_prices", price_data)
                    count += 1
                except (KeyError, ValueError, TypeError) as e:
                    log.error("Error parsing mandi price record: %s", e)
                    continue
        return count

    async def ingest_recent_prices(
        self, state: str, district: str, commodity: str
    ) -> int:
        """
        Entry point: Fetch and store recent prices for a specific region and crop.
        """
        try:
            data = await self.fetch_prices(
                state=state, district=district, commodity=commodity
            )
            records = data.get("records", [])

            if not records:
                log.info("No records found for criteria: %s, %s, %s", state, district, commodity)
                return 0

            # Offload persistence to thread if needed, but since it's a few records, 
            # direct sync call in this simple script is fine for task execution.
            count = self._persist_records(records)
            log.info("Successfully ingested %d mandi price records.", count)
            return count

        except Exception as e:
            log.error("Mandi price ingestion failed: %s", e)
            return 0


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    async def test_run() -> None:
        ingester = MandiPriceIngester()
        # Sample run for Punjab Wheat
        await ingester.ingest_recent_prices("Punjab", "Ludhiana", "Wheat")

    asyncio.run(test_run())
