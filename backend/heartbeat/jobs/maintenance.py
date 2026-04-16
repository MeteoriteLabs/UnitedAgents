"""United Agents — Maintenance jobs.

Per AGENT_SPEC.md §6, D-13. Both preserved as scaffolded no-ops.
Real task-timeout filtering is done at the API query layer (GOTCHAS §4.5).
"""

import logging

logger = logging.getLogger("heartbeat.jobs.maintenance")


async def task_timeout_check(client=None):
    """Release tasks claimed >24h. Currently no-op (AGENT_SPEC §6).
    Real enforcement: API layer filters stale claims at query time.
    """
    logger.debug("[MAINTENANCE] task_timeout_check — no-op (reserved)")


async def compute_urgency_scores(client=None):
    """Recompute per-community urgency scores. Currently no-op (AGENT_SPEC §6).
    Real urgency: assigned inline on post creation via src/utils.py.
    """
    logger.debug("[MAINTENANCE] compute_urgency_scores — no-op (reserved)")
