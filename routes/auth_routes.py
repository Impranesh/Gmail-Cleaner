"""
OAuth and authentication routes.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from auth.oauth import get_authorization_url, get_credentials_from_callback
from sessions.manager import create_session, update_session, get_session

router = APIRouter()


@router.post("/start")
def start(
    unread: str = Form(None),
    promotions: str = Form(None),
    social: str = Form(None),
    updates: str = Form(None),
    age: str = Form(""),
    restore: str = Form(None)
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
    
    # Create session
    session_id = create_session(queries, bool(restore))
    
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
