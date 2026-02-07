"""
Gmail service module - all Gmail API interactions.
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json


def get_preview(service, query: str) -> list:
    """Get preview of emails matching the query."""
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=10
    ).execute()
    
    previews = []
    for msg in results.get("messages", []):
        data = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='metadata',
            metadataHeaders=['Subject', 'From']
        ).execute()
        
        headers = {h['name']: h['value'] for h in data['payload']['headers']}
        previews.append({
            "id": msg['id'],
            "subject": headers.get("Subject", "No Subject"),
            "from": headers.get("From", "Unknown")
        })
    
    return previews


def move_to_trash(service, ids: list) -> None:
    """Move messages to trash."""
    if not ids:
        return
    
    service.users().messages().batchModify(
        userId='me',
        body={'ids': ids, 'addLabelIds': ['TRASH']}
    ).execute()


def restore_from_trash(service, ids: list) -> None:
    """Restore messages from trash to inbox."""
    if not ids:
        return
    
    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': ids,
            'removeLabelIds': ['TRASH'],
            'addLabelIds': ['INBOX']
        }
    ).execute()


def list_messages(service, query: str, max_results: int = 500, page_token: str = None) -> tuple:
    """List messages matching query. Returns (messages, next_page_token)."""
    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=max_results,
        pageToken=page_token
    ).execute()
    
    messages = results.get('messages', [])
    next_token = results.get('nextPageToken')
    
    return messages, next_token


def restore_read_from_trash(service) -> int:
    """Restore all read emails from trash. Returns count of restored emails."""
    total_restored = 0
    next_page_token = None
    
    while True:
        messages, next_page_token = list_messages(
            service,
            q="in:trash -is:unread",
            page_token=next_page_token
        )
        
        if not messages:
            break
        
        ids = [m['id'] for m in messages]
        restore_from_trash(service, ids)
        total_restored += len(ids)
        
        if not next_page_token:
            break
    
    return total_restored


def build_service(credentials_json: str):
    """Build Gmail service from credentials JSON."""
    creds = Credentials.from_authorized_user_info(json.loads(credentials_json))
    return build('gmail', 'v1', credentials=creds)
