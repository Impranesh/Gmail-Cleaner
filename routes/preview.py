from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import Template
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json, os

router = APIRouter()

def get_preview(service, query):
    results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
    previews = []

    for msg in results.get("messages", []):
        data = service.users().messages().get(
            userId='me', id=msg['id'], format='metadata',
            metadataHeaders=['Subject','From']
        ).execute()

        headers = {h['name']:h['value'] for h in data['payload']['headers']}
        previews.append({
            "id": msg['id'],
            "subject": headers.get("Subject","No Subject"),
            "from": headers.get("From","Unknown")
        })

    return previews


@router.get("/preview", response_class=HTMLResponse)
def preview(query: str, request: Request):
    session_id = request.cookies.get("session_id")
    session = request.app.state.SESSIONS.get(session_id)

    creds = Credentials.from_authorized_user_info(json.loads(session["creds"]))
    service = build('gmail', 'v1', credentials=creds)

    mails = get_preview(service, query)

    with open("templates/preview.html") as f:
        html = Template(f.read()).render(mails=mails)

    return HTMLResponse(html)
