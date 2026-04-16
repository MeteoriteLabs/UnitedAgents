"""United Agents — USGS Water Services data source.

Per AGENT_SPEC.md §10. Default parameter codes: discharge, DO, pH, temp, turbidity.
"""

import logging
from typing import Any, Dict

import httpx

from heartbeat.sources.base import DataSource

logger = logging.getLogger("heartbeat.sources.usgs")

DEFAULT_PARAMETER_CODES = {
    "00060": "discharge_cfs",
    "00300": "dissolved_oxygen_mg_l",
    "00400": "ph",
    "00010": "temperature_c",
    "63680": "turbidity_ntu",
}


class USGSWaterServices(DataSource):
    """USGS Water Services instantaneous values."""

    async def fetch_latest(self, config: dict) -> Dict[str, Any]:
        try:
            station_id = config.get("station_id")
            if not station_id:
                return {"error": "No station_id configured"}

            base_url = config.get("base_url", "https://waterservices.usgs.gov/nwis/iv/")
            param_codes = config.get("parameter_codes", list(DEFAULT_PARAMETER_CODES.keys()))

            params = {
                "format": "json",
                "sites": station_id,
                "parameterCd": ",".join(param_codes),
                "siteStatus": "active",
            }

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
                data = resp.json()

            result = {"station_id": station_id}
            time_series = data.get("value", {}).get("timeSeries", [])

            for ts in time_series:
                var_code = ts.get("variable", {}).get("variableCode", [{}])[0].get("value", "")
                param_name = DEFAULT_PARAMETER_CODES.get(var_code, var_code)
                values = ts.get("values", [{}])[0].get("value", [])
                if values:
                    latest = values[-1]
                    try:
                        result[param_name] = float(latest.get("value", 0))
                    except (ValueError, TypeError):
                        result[param_name] = latest.get("value")
                    result[f"{param_name}_timestamp"] = latest.get("dateTime", "")

            return result

        except Exception as e:
            logger.warning(f"USGS fetch failed for station {config.get('station_id')}: {e}")
            return {"error": str(e)}
