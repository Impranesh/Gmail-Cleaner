from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Template
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json, os
from datetime import datetime
from services.ai_rules import detect_spam_bayesian, calculate_email_stats

router = APIRouter()

def get_preview(service, query, max_results=15):
    """Get preview of emails matching query"""
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    previews = []

    for msg in results.get("messages", []):
        data = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['Subject','From','Date']
        ).execute()

        headers = {h['name']:h['value'] for h in data['payload']['headers']}
        preview_item = {
            "id": msg['id'],
            "subject": headers.get("Subject","No Subject"),
            "from": headers.get("From","Unknown"),
            "date": headers.get("Date", "Unknown")
        }
        
        # Use Bayesian spam detection
        try:
            is_spam, confidence, explanation = detect_spam_bayesian(
                preview_item["subject"],
                preview_item["from"],
                ""
            )
            preview_item["spam_score"] = round(confidence * 100)
            preview_item["is_spam"] = is_spam
            preview_item["spam_explanation"] = explanation
        except Exception as e:
            preview_item["spam_score"] = 0
            preview_item["is_spam"] = False
            preview_item["spam_explanation"] = ""
        
        previews.append(preview_item)

    return previews


@router.get("/preview", response_class=HTMLResponse)
def preview(query: str, request: Request):
    """Show preview of emails before deletion"""
    session_id = request.cookies.get("session_id")
    session = request.app.state.SESSIONS.get(session_id)

    creds = Credentials.from_authorized_user_info(json.loads(session["creds"]))
    service = build('gmail', 'v1', credentials=creds)

    mails = get_preview(service, query, max_results=15)
    
    # Calculate stats
    total = len(mails)
    spam_count = sum(1 for m in mails if m.get("is_spam"))
    
    with open("templates/preview.html") as f:
        html = Template(f.read()).render(
            mails=mails,
            query=query,
            total=total,
            spam_count=spam_count
        )

    return HTMLResponse(html)


@router.post("/api/preview-stats")
async def preview_stats(request: Request):
    """Get statistics for emails to be deleted"""
    data = await request.json()
    query = data.get("query", "")
    
    session_id = request.cookies.get("session_id")
    session = request.app.state.SESSIONS.get(session_id)
    
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=401)

    try:
        creds = Credentials.from_authorized_user_info(json.loads(session["creds"]))
        service = build('gmail', 'v1', credentials=creds)
        
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        total_count = results.get('resultSizeEstimate', 0)
        
        return JSONResponse({
            "total_emails": total_count,
            "estimated_storage_mb": round(total_count * 0.05, 2),
            "query": query
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/session-history")
async def session_history(request: Request):
    """Get cleanup session history for undo functionality"""
    session_id = request.cookies.get("session_id")
    session = request.app.state.SESSIONS.get(session_id)
    
    if not session:
        return JSONResponse({"error": "Session not found"}, status_code=401)
    
    history = session.get("cleanup_history", [])
    return JSONResponse({"history": history})
