"""
Progress page and streaming progress route.
"""
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path
from services.gmail_service import build_service, list_messages, move_to_trash, restore_read_from_trash
from sessions.manager import get_session

router = APIRouter()

# Template path
template_path = Path(__file__).parent.parent / "templates" / "progress.html"


@router.get("/progress_page")
def progress_page():
    """Display the progress page."""
    return FileResponse(template_path)


@router.get("/progress")
async def progress(request: Request):
    """Stream cleaning progress to the client."""
    
    async def event_stream():
        session_id = request.cookies.get("session_id")
        session = get_session(session_id)
        
        if not session:
            yield "data: Error: Session not found\n\n"
            return
        
        # Build Gmail service from credentials
        service = build_service(session["creds"])
        
        total_deleted = 0
        found_any = False
        
        yield "data: Starting cleanup...\n\n"
        
        # Process each query
        for query in session["queries"]:
            yield f"data: Processing {query}...\n\n"
            next_page_token = None
            
            while True:
                messages, next_page_token = list_messages(service, query, page_token=next_page_token)
                
                if not messages:
                    break
                
                found_any = True
                ids = [m['id'] for m in messages]
                move_to_trash(service, ids)
                
                total_deleted += len(ids)
                yield f"data: Deleted {total_deleted} emails...\n\n"
                
                await asyncio.sleep(0.2)
                
                if not next_page_token:
                    break
        
        # Safety restore: restore read emails from trash
        if session.get("restore_enabled"):
            restored_count = restore_read_from_trash(service)
            yield f"data: Restored {restored_count} read emails from Trash 🔁\n\n"
        
        # Final message
        if not found_any:
            yield "data: No matching emails found 🎉\n\n"
        else:
            yield f"data: DONE. Total deleted: {total_deleted}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
