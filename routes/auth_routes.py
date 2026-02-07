"""
OAuth and authentication routes.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from auth.oauth import get_authorization_url, get_credentials_from_callback
from sessions.manager import create_session, update_session, get_session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
from datetime import datetime

router = APIRouter()


@router.post("/start")
def start(
    unread: str = Form(None),
    promotions: str = Form(None),
    social: str = Form(None),
    updates: str = Form(None),
    age: str = Form(""),
    restore: str = Form(None),
    enable_spam_detection: str = Form(None),
    enable_preview: str = Form(None)
):
    """
    Start the cleaning process - build filters and initiate OAuth.
    """
    # Build query list with safety filter (only unread emails)
    base_filter = "is:unread"
    queries = []
    
    if unread:
        queries.append(base_filter)
    
    if promotions:
        queries.append(f"{base_filter} category:promotions")
    
    if social:
        queries.append(f"{base_filter} category:social")
    
    if updates:
        queries.append(f"{base_filter} category:updates")
    
    # Add age filter if selected
    if age:
        queries = [q + f" older_than:{age}" for q in queries]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
    queries = unique_queries
    
    # If no specific filters selected, default to unread only
    if not queries:
        queries = [base_filter]
        if age:
            queries = [f"{base_filter} older_than:{age}"]
    
    # Create session with new options
    session_id = create_session(
        queries, 
        bool(restore),
        enable_spam_detection=bool(enable_spam_detection),
        enable_preview=bool(enable_preview)
    )
    
    # Get OAuth authorization URL
    auth_url, state = get_authorization_url()
    update_session(session_id, {"state": state})
    
    # Redirect to OAuth with session cookie
    response = RedirectResponse(auth_url)
    response.set_cookie("session_id", session_id, httponly=True, secure=True)
    
    return response


@router.get("/auth/callback")
def callback(request: Request):
    """
    Handle OAuth callback - exchange code for credentials.
    """
    session_id = request.cookies.get("session_id")
    session = get_session(session_id)
    
    if not session:
        return RedirectResponse("/")
    
    # Exchange auth code for credentials
    creds = get_credentials_from_callback(
        str(request.url),
        session["state"]
    )
    
    # Store credentials in session
    update_session(session_id, {"creds": creds.to_json()})
    
    return RedirectResponse("/progress_page")


@router.post("/api/undo-session")
async def undo_session(request: Request):
    """
    Restore emails from last cleanup session (undo functionality).
    """
    session_id = request.cookies.get("session_id")
    session = get_session(session_id)
    
    if not session:
        return JSONResponse({"error": "Session not found", "success": False}, status_code=401)
    
    try:
        cleanup_history = session.get("cleanup_history", [])
        
        if not cleanup_history:
            return JSONResponse({
                "success": False,
                "message": "No cleanup history found"
            })
        
        last_cleanup = cleanup_history[-1]
        deleted_ids = last_cleanup.get("email_ids", [])
        
        if not deleted_ids:
            return JSONResponse({
                "success": False,
                "message": "No emails to restore from last session"
            })
        
        # Restore emails from trash
        creds = Credentials.from_authorized_user_info(json.loads(session["creds"]))
        service = build('gmail', 'v1', credentials=creds)
        
        restored_count = 0
        for email_id in deleted_ids:
            try:
                service.users().messages().untrash(userId='me', id=email_id).execute()
                restored_count += 1
            except Exception as e:
                print(f"Failed to restore email {email_id}: {e}")
                continue
        
        return JSONResponse({
            "success": True,
            "emails_restored": restored_count,
            "message": f"Restored {restored_count} emails"
        })
        
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": str(e)
        }, status_code=500)
