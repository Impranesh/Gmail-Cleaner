from fastapi import APIRouter, Request
from services.gmail_service import get_preview

router = APIRouter()

@router.get("/preview")
def preview(query: str, request: Request):
    service = request.app.state.get_gmail_service(request)
    return get_preview(service, query)
