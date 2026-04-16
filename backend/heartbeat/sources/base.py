"""United Agents — Data source base class.

All sources inherit from DataSource. Never raise — return {error: ...}.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    async def fetch_latest(self, config: dict) -> Dict[str, Any]:
        """Fetch latest data. Must never raise — return {error: ...} on failure."""
        ...
