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
        try:
            service = build_service(session["creds"])
        except Exception as e:
            yield f"data: Error building service: {str(e)}\n\n"
            return
        
        total_deleted = 0
        found_any = False
        spam_detected = 0
        
        yield "data: 🔍 Starting inbox cleanup...\n\n"
        
        # Get unique queries to avoid duplicates
        queries = list(set(session.get("queries", [])))
        
        if not queries:
            yield "data: No filters selected\n\n"
            return
        
        # Check if spam detection is enabled
        spam_detection_enabled = session.get("enable_spam_detection", False)
        if spam_detection_enabled:
            yield "data: 🤖 AI Spam Detection enabled\n\n"
            from services.ai_rules import detect_spam_bayesian
        
        # Process each query only once
        for i, query in enumerate(queries, 1):
            yield f"data: [{i}/{len(queries)}] Processing: {query}\n\n"
            next_page_token = None
            query_deleted = 0
            query_spam = 0
            
            try:
                while True:
                    messages, next_page_token = list_messages(service, query, page_token=next_page_token)
                    
                    if not messages:
                        if query_deleted > 0:
                            if spam_detection_enabled:
                                yield f"data: ✓ '{query}': {query_deleted} deleted ({query_spam} flagged as spam)\n\n"
                            else:
                                yield f"data: ✓ '{query}': {query_deleted} deleted\n\n"
                        break
                    
                    found_any = True
                    ids = [m['id'] for m in messages]
                    
                    # Analyze spam if enabled
                    if spam_detection_enabled:
                        for msg in messages:
                            try:
                                subject = msg['payload']['headers'].get('Subject', '')
                                sender = msg['payload']['headers'].get('From', '')
                                is_spam, confidence, _ = detect_spam_bayesian(subject, sender, "")
                                if is_spam:
                                    query_spam += 1
                            except:
                                pass
                    
                    move_to_trash(service, ids)
                    
                    query_deleted += len(ids)
                    total_deleted += len(ids)
                    spam_detected += query_spam
                    
                    if spam_detection_enabled:
                        yield f"data: Progress: {total_deleted} emails deleted ({spam_detected} spam detected)\n\n"
                    else:
                        yield f"data: Progress: {total_deleted} emails deleted...\n\n"
                    
                    await asyncio.sleep(0.2)
                    
                    if not next_page_token:
                        break
            except Exception as e:
                yield f"data: Error processing '{query}': {str(e)}\n\n"
                continue
        
        # Safety restore: restore read emails from trash
        if session.get("restore_enabled"):
            try:
                yield "data: ⏮️ Restoring read emails from Trash...\n\n"
                restored_count = restore_read_from_trash(service)
                yield f"data: ✓ Restored {restored_count} read emails\n\n"
            except Exception as e:
                yield f"data: Warning during restore: {str(e)}\n\n"
        
        # Final message with detailed stats
        if not found_any:
            yield "data: ✅ DONE. No matching emails found\n\n"
        else:
            if spam_detection_enabled:
                spam_percent = int((spam_detected / total_deleted) * 100) if total_deleted > 0 else 0
                yield f"data: ✅ DONE. Total deleted: {total_deleted} emails total | Spam: {spam_detected} ({spam_percent}%)\n\n"
            else:
                yield f"data: ✅ DONE. Total deleted: {total_deleted} emails total\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
