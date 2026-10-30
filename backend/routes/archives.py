from fastapi import APIRouter, Query
from ..services import services

router = APIRouter(prefix="/api")


@router.get("/archives")
def archive_history(q: str = "", limit: int = Query(30, ge=1, le=30)):
    return {"items": services.store.search_archives(q, limit)}
