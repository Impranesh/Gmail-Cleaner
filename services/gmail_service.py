# All Gmail API calls.

from googleapiclient.discovery import build

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

def move_to_trash(service, ids):
    service.users().messages().batchModify(
        userId='me',
        body={'ids': ids, 'addLabelIds': ['TRASH']}
    ).execute()

def restore_from_trash(service, ids):
    service.users().messages().batchModify(
        userId='me',
        body={'ids': ids, 'removeLabelIds': ['TRASH']}
    ).execute()
