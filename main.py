from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, asyncio, json, secrets

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

client_config = json.loads(os.environ["GOOGLE_CLIENT_CONFIG_JSON"])
REDIRECT_URI = os.environ["REDIRECT_URI"]

# In-memory user session store
SESSIONS = {}

# ================= HOME PAGE =================
@app.get("/", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>Gmail Cleaner Pro</title>
        <style>
            body { font-family: Arial; background:#f4f6f9; padding:40px; text-align:center; }
            .box { background:white; padding:30px; border-radius:10px; width:450px; margin:auto; box-shadow:0 0 10px rgba(0,0,0,0.1); }
            label { display:block; text-align:left; margin:10px 0; }
            select, button { padding:8px; margin-top:10px; width:100%; }
            button { background:#4285F4; color:white; border:none; border-radius:5px; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>🧹 Gmail Cleaner Pro</h2>
            <form action="/start" method="post">
                <label><input type="checkbox" name="unread" checked> Unread Emails</label>
                <label><input type="checkbox" name="promotions"> Promotions</label>
                <label><input type="checkbox" name="social"> Social</label>
                <label><input type="checkbox" name="updates"> Updates</label>

                <label>📅 Delete emails older than:</label>
                <select name="age">
                    <option value="">No filter</option>
                    <option value="7d">1 Week</option>
                    <option value="1m">1 Month</option>
                    <option value="1y">1 Year</option>
                </select>

                <label><input type="checkbox" name="restore" checked> 🔁 Enable Safety Restore (Recommended)</label>

                <button type="submit">Login & Clean</button>
            </form>
        </div>
    </body>
    </html>
    """


# ================= START OAUTH =================
@app.post("/start")
def start(unread: str = Form(None),
          promotions: str = Form(None),
          social: str = Form(None),
          updates: str = Form(None),
          age: str = Form(""),
          restore: str = Form(None)):

    # GLOBAL SAFETY RULE → never delete read mails
    base_filter = "is:unread"

    queries = []

    # User selected filters
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
    session_id = secrets.token_hex(16)
    SESSIONS[session_id] = {
        "queries": queries,
        "restore_enabled": bool(restore)
    }

    # Start OAuth flow
    flow = Flow.from_client_config(
        client_config,
        SCOPES,
        redirect_uri=REDIRECT_URI
    )

    auth_url, state = flow.authorization_url(prompt='consent')
    SESSIONS[session_id]["state"] = state

    response = RedirectResponse(auth_url)
    response.set_cookie("session_id", session_id, httponly=True)

    return response

# ================= CALLBACK =================
@app.get("/auth/callback")
def callback(request: Request):
    session_id = request.cookies.get("session_id")
    session = SESSIONS.get(session_id)

    flow = Flow.from_client_config(client_config, SCOPES, state=session["state"], redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=str(request.url))

    session["creds"] = flow.credentials.to_json()
    return RedirectResponse("/progress_page")

# ================= PROGRESS PAGE =================
@app.get("/progress_page", response_class=HTMLResponse)
def progress_page():
    return """
    <html>
    <head>
        <title>Cleaning...</title>
        <style>
            body { font-family: Arial; background:#f4f6f9; text-align:center; padding:40px; }
            .box { background:white; padding:30px; border-radius:10px; width:500px; margin:auto; box-shadow:0 0 10px rgba(0,0,0,0.1); }
            #barWrap { background:#ddd; height:20px; border-radius:10px; }
            #bar { height:20px; width:0%; background:#4285F4; border-radius:10px; }
            ul { text-align:left; max-height:200px; overflow:auto; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Cleaning Your Inbox...</h2>
            <div id="barWrap"><div id="bar"></div></div>
            <p id="status">Starting...</p>
            <ul id="log"></ul>
        </div>

        <script>
            var source = new EventSource("/progress");
            let percent = 0;
            source.onmessage = function(event){
                let msg = event.data;
                document.getElementById("status").innerText = msg;
                document.getElementById("log").innerHTML += "<li>" + msg + "</li>";
                percent += 5;
                document.getElementById("bar").style.width = Math.min(percent,100) + "%";
                if(msg.includes("DONE") || msg.includes("No matching emails")){
                    source.close();
                    document.getElementById("bar").style.width = "100%";
                }
            };
        </script>
    </body>
    </html>
    """

# ================= RESTORE READ EMAILS =================
def restore_read_from_trash(service):
    next_page_token = None
    restored = 0

    while True:
        results = service.users().messages().list(
            userId='me',
            q="in:trash -is:unread",
            maxResults=500,
            pageToken=next_page_token
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            break

        ids = [m['id'] for m in messages]

        service.users().messages().batchModify(
            userId='me',
            body={
                "ids": ids,
                "removeLabelIds": ["TRASH"],
                "addLabelIds": ["INBOX"]
            }
        ).execute()

        restored += len(ids)

        next_page_token = results.get('nextPageToken')
        if not next_page_token:
            break

    return restored

# ================= CLEANING STREAM =================
@app.get("/progress")
async def progress(request: Request):

    async def event_stream():
        session_id = request.cookies.get("session_id")
        session = SESSIONS.get(session_id)

        creds = Credentials.from_authorized_user_info(json.loads(session["creds"]))
        service = build('gmail', 'v1', credentials=creds)

        total_deleted = 0
        found_any = False

        yield "data: Starting cleanup...\n\n"

        for query in session["queries"]:
            yield f"data: Cleaning {query}...\n\n"
            next_page_token = None

            while True:
                results = service.users().messages().list(userId='me', q=query, maxResults=500, pageToken=next_page_token).execute()
                messages = results.get('messages', [])
                if not messages:
                    break

                found_any = True
                ids = [m['id'] for m in messages]

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

        # 🔁 SAFETY RESTORE
        restored_count = restore_read_from_trash(service)

        if not found_any:
            yield "data: No matching emails found 🎉\n\n"
        else:
            yield f"data: DONE. Total deleted: {total_deleted}\n\n"

        yield f"data: Restored {restored_count} read emails from Trash 🔁\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
