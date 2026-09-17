"""Analytics endpoints for the initial baseline."""

from fastapi import APIRouter

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary")
def summary() -> dict[str, object]:
    """Return a stable empty analytics shape until incident persistence is enabled."""

    return {"total_incidents": 0, "by_status": {"OK": 0, "WARNING": 0, "CRITICAL": 0}}