from fastapi import FastAPI, Form, Request, Response, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, asyncio, json

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

REDIRECT_URI = os.environ.get(
    "REDIRECT_URI",
    "https://gmail-cleaner-latest.onrender.com/auth/callback"
)

CLIENT_SECRETS_FILE = os.environ.get('CLIENT_SECRETS_FILE', 'cred_web.json')

# ---------------- HOME PAGE ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """<html>... SAME UI HTML ...</html>"""  # keep your UI code unchanged


# ---------------- START CLEANING ----------------
@app.post("/start")
def start(response: Response,
          unread: str = Form(None), promotions: str = Form(None),
          social: str = Form(None), updates: str = Form(None),
          age: str = Form("")):

    selected = []
    if unread: selected.append("is:unread")
    if promotions: selected.append("category:promotions")
    if social: selected.append("category:social")
    if updates: selected.append("category:updates")

    time_filter = f" older_than:{age}" if age else ""
    queries = [q + time_filter for q in selected]
    os.environ['CLEAN_QUERIES'] = ",".join(queries)

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, state = flow.authorization_url(prompt='consent')
    response.set_cookie("oauth_state", state)

    return RedirectResponse(auth_url)


# ---------------- CALLBACK ----------------
@app.get("/auth/callback")
def callback(request: Request, oauth_state: str = Cookie(None)):

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=oauth_state,
        redirect_uri=REDIRECT_URI
    )

    flow.fetch_token(authorization_response=str(request.url))
    creds = flow.credentials

    os.environ["USER_TOKEN"] = creds.to_json()
    return RedirectResponse("/progress_page")


# ---------------- PROGRESS PAGE ----------------
@app.get("/progress_page", response_class=HTMLResponse)
def progress_page():
    return """<html>... SAME PROGRESS PAGE HTML ...</html>"""


# ---------------- STREAM CLEANING PROGRESS ----------------
@app.get("/progress")
async def progress():

    async def event_stream():
        creds = Credentials.from_authorized_user_info(
            json.loads(os.environ["USER_TOKEN"])
        )
        service = build('gmail', 'v1', credentials=creds)
        queries = os.environ.get("CLEAN_QUERIES", "").split(",")

        total_deleted = 0
        found_any = False

        yield "data: Starting cleanup...\n\n"

        for query in queries:
            next_page_token = None
            while True:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=500, pageToken=next_page_token
                ).execute()

                messages = results.get('messages', [])
                if not messages:
                    break

                found_any = True
                ids = [msg['id'] for msg in messages]

                service.users().messages().batchModify(
                    userId='me',
                    body={'ids': ids, 'addLabelIds': ['TRASH']}
                ).execute()

                total_deleted += len(ids)
                yield f"data: Deleted {total_deleted} emails...\n\n"
                await asyncio.sleep(0.2)

                next_page_token = results.get('nextPageToken')
                if not next_page_token:
                    break

        if not found_any:
            yield "data: No matching emails found 🎉\n\n"
        else:
            yield f"data: DONE. Total deleted: {total_deleted}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
