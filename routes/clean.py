from fastapi import APIRouter, Request
from services.gmail_service import  move_to_trash, restore_from_trash

router = APIRouter()

@router.post("/clean")
def clean(ids: list[str], request: Request):
    service = request.app.state.get_gmail_service(request)
    request.session["last_deleted"] = ids
    move_to_trash(service, ids)
    return {"status":"Deleted"}

@router.post("/undo")
def undo(request: Request):
    service = request.app.state.get_gmail_service(request)
    ids = request.session.get("last_deleted", [])
    restore_from_trash(service, ids)
    return {"status":"Restored"}
