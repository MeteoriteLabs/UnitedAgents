"""United Agents — Global Forest Watch data source.

Per AGENT_SPEC.md §10. Deforestation alerts + active fires.
"""

import logging
from typing import Any, Dict

import httpx

from heartbeat.sources.base import DataSource

logger = logging.getLogger("heartbeat.sources.gfw")


class GlobalForestWatch(DataSource):
    """Global Forest Watch API — deforestation alerts and active fires."""

    async def fetch_latest(self, config: dict) -> Dict[str, Any]:
        try:
            api_key = config.get("api_key")
            if not api_key:
                return {"error": "No GFW api_key configured"}

            geostore_id = config.get("geostore_id")
            bbox = config.get("bbox")
            if not geostore_id and not bbox:
                return {"error": "Need geostore_id or bbox [minLon, minLat, maxLon, maxLat]"}

            headers = {"x-api-key": api_key}
            result = {}

            async with httpx.AsyncClient(timeout=20) as client:
                # Deforestation alerts
                deforest_url = "https://data-api.globalforestwatch.org/v1/forest-change/deforestation-alerts"
                params = {}
                if geostore_id:
                    params["geostore_id"] = geostore_id
                elif bbox:
                    params["bbox"] = ",".join(str(b) for b in bbox)

                try:
                    resp = await client.get(deforest_url, headers=headers, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        result["deforestation_alerts"] = data.get("data", {}).get("attributes", {}).get("value", 0)
                        result["deforestation_area_ha"] = data.get("data", {}).get("attributes", {}).get("areaHa", 0)
                except Exception as e:
                    result["deforestation_error"] = str(e)

                # Active fires
                fires_url = "https://data-api.globalforestwatch.org/v1/fires/active"
                try:
                    resp = await client.get(fires_url, headers=headers, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        result["active_fires"] = data.get("data", {}).get("attributes", {}).get("value", 0)
                except Exception as e:
                    result["fires_error"] = str(e)

            return result

        except Exception as e:
            logger.warning(f"GFW fetch failed: {e}")
            return {"error": str(e)}
