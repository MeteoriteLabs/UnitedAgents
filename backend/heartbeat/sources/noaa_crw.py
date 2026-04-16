"""United Agents — NOAA Coral Reef Watch data source.

Per AGENT_SPEC.md §10. Extracts SST, SST anomaly, DHW, hotspot, BAA, alert level.
"""

import logging
from typing import Any, Dict

import httpx

from heartbeat.sources.base import DataSource

logger = logging.getLogger("heartbeat.sources.noaa_crw")


class NOAACRWatch(DataSource):
    """NOAA Coral Reef Watch station data."""

    async def fetch_latest(self, config: dict) -> Dict[str, Any]:
        try:
            station_id = config.get("station_id")
            if not station_id:
                return {"error": "No station_id configured"}

            base_url = config.get("base_url", "https://coralreefwatch.noaa.gov/product/vs/data")
            url = f"{base_url}/{station_id}.json"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                if resp.status_code == 404:
                    # Fallback to CSV
                    csv_url = f"{base_url}/{station_id}.csv"
                    resp = await client.get(csv_url)
                    if resp.status_code == 200:
                        return self._parse_csv(resp.text, station_id)
                    return {"error": f"Station {station_id} not found (JSON or CSV)"}
                resp.raise_for_status()
                data = resp.json()

            # Extract fields
            result = {"station_id": station_id}
            for key in ("sst", "sst_anomaly", "dhw", "hotspot", "baa", "alert_level"):
                if key in data:
                    try:
                        result[key] = float(data[key])
                    except (ValueError, TypeError):
                        result[key] = data[key]

            return result

        except Exception as e:
            logger.warning(f"NOAA CRW fetch failed for station {config.get('station_id')}: {e}")
            return {"error": str(e)}

    def _parse_csv(self, csv_text: str, station_id: str) -> Dict[str, Any]:
        """Parse CSV fallback. Assumes header row + data rows."""
        try:
            lines = csv_text.strip().split("\n")
            if len(lines) < 2:
                return {"error": "CSV has no data rows"}
            headers = [h.strip().lower() for h in lines[0].split(",")]
            values = lines[-1].split(",")  # Latest row
            result = {"station_id": station_id}
            for h, v in zip(headers, values):
                v = v.strip()
                if h in ("sst", "sst_anomaly", "dhw", "hotspot", "baa", "alert_level"):
                    try:
                        result[h] = float(v)
                    except ValueError:
                        result[h] = v
            return result
        except Exception as e:
            return {"error": f"CSV parse failed: {e}"}
