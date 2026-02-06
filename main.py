from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, json, asyncio

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
REDIRECT_URI = os.environ.get("REDIRECT_URI")
client_config = json.loads(os.environ.get("GOOGLE_CLIENT_CONFIG_JSON"))

SAFETY_LIMIT = 2000  # Prevent mass accidental deletion

# ---------------- HOME ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>Gmail Smart Cleaner</title>
        <style>
            body { font-family:'Segoe UI'; background:#121212; color:white; text-align:center; padding:40px;}
            .card { background:#1e1e1e; padding:30px; border-radius:12px; width:450px; margin:auto; }
            button { padding:12px; width:100%; background:#4285F4; color:white; border:none; border-radius:8px; font-size:16px;}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🧹 Gmail Smart Cleaner</h2>
            <form action="/start" method="post">
                <button type="submit">Login with Google</button>
            </form>
        </div>
    </body>
    </html>
    """

# ---------------- LOGIN START ----------------
@app.post("/start")
def start(response: Response):
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, state = flow.authorization_url(prompt='consent')

    response = RedirectResponse(auth_url)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="Lax")
    return response

# ---------------- CALLBACK ----------------
@app.get("/auth/callback")
def callback(request: Request, oauth_state: str = Cookie(None)):
    flow = Flow.from_client_config(client_config, scopes=SCOPES, state=oauth_state, redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=str(request.url))
    creds = flow.credentials

    service = build('gmail', 'v1', credentials=creds)
    profile = service.users().getProfile(userId='me').execute()
    email = profile['emailAddress']

    response = RedirectResponse("/dashboard")
    response.set_cookie("user_token", creds.to_json(), httponly=True, secure=True, samesite="Lax")
    response.set_cookie("user_email", email)
    return response

# ---------------- DASHBOARD ----------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(user_email: str = Cookie("")):
    return f"""
    <html>
    <head>
        <title>Dashboard</title>
        <style>
            body {{ font-family:'Segoe UI'; background:#121212; color:white; text-align:center; padding:40px;}}
            .card {{ background:#1e1e1e; padding:30px; border-radius:12px; width:500px; margin:auto; }}
            button {{ padding:10px 20px; margin-top:15px; background:#34A853; border:none; border-radius:6px; color:white; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>📊 Gmail Cleaner Dashboard</h2>
            <p>Logged in as <b>{user_email}</b></p>
            <button onclick="window.location='/preview_page'">Preview Cleanup</button>
            <button onclick="window.location='/progress_page'">Run Cleanup</button>
            <button onclick="window.location='/logout'">Logout</button>
        </div>
    </body>
    </html>
    """

# ---------------- PREVIEW PAGE ----------------
@app.get("/preview_page", response_class=HTMLResponse)
def preview_page():
    return """
    <html>
    <body style="background:#121212;color:white;text-align:center;font-family:Segoe UI;">
        <h2>Preview Email Counts</h2>
        <ul id="list"></ul>
        <button onclick="window.location='/dashboard'">Back</button>
        <script>
            fetch("/preview_counts").then(r=>r.json()).then(data=>{
                let ul=document.getElementById("list");
                for(let k in data) ul.innerHTML += `<li>${k} → ${data[k]} emails</li>`;
            });
        </script>
    </body>
    </html>
    """

# ---------------- PREVIEW COUNTS ----------------
@app.get("/preview_counts")
def preview_counts(user_token: str = Cookie(None)):
    creds = Credentials.from_authorized_user_info(json.loads(user_token))
    service = build('gmail', 'v1', credentials=creds)

    queries = ["is:unread", "category:promotions", "category:social", "category:updates"]
    counts = {}

    for q in queries:
        res = service.users().messages().list(userId='me', q=q, maxResults=1).execute()
        counts[q] = res.get('resultSizeEstimate', 0)

    return counts

# ---------------- CLEANING PAGE ----------------
@app.get("/progress_page", response_class=HTMLResponse)
def progress_page():
    return """
    <html>
    <body style="background:#121212;color:white;text-align:center;font-family:Segoe UI;">
        <h2>Cleaning in progress...</h2>
        <div style="background:#333;height:20px;border-radius:10px;">
            <div id="bar" style="height:20px;width:0%;background:#34A853;border-radius:10px;"></div>
        </div>
        <ul id="log"></ul>
        <script>
            let source=new EventSource("/progress");
            let percent=0;
            source.onmessage=function(e){
                document.getElementById("log").innerHTML+="<li>"+e.data+"</li>";
                percent+=5;
                document.getElementById("bar").style.width=Math.min(percent,100)+"%";
            }
        </script>
    </body>
    </html>
    """

# ---------------- CLEANING LOGIC ----------------
@app.get("/progress")
async def progress(user_token: str = Cookie(None)):
    async def event_stream():
        creds = Credentials.from_authorized_user_info(json.loads(user_token))
        service = build('gmail', 'v1', credentials=creds)

        queries = ["is:unread", "category:promotions", "category:social", "category:updates"]
        total_deleted = 0

        yield "data: Starting cleanup...\n\n"

        for q in queries:
            next_token=None
            deleted=0
            while True:
                res = service.users().messages().list(userId='me', q=q, maxResults=500, pageToken=next_token).execute()
                msgs=res.get('messages',[])
                if not msgs: break

                if total_deleted > SAFETY_LIMIT:
                    yield "data: Safety stop triggered!\n\n"
                    return

                ids=[m['id'] for m in msgs]
                service.users().messages().batchModify(userId='me', body={'ids':ids,'addLabelIds':['TRASH']}).execute()

                deleted+=len(ids)
                total_deleted+=len(ids)
                yield f"data: {q} → {deleted} deleted\n\n"
                next_token=res.get('nextPageToken')
                if not next_token: break

        yield f"data: DONE. TOTAL DELETED: {total_deleted}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ---------------- LOGOUT ----------------
@app.get("/logout")
def logout():
    r = RedirectResponse("/")
    r.delete_cookie("user_token")
    r.delete_cookie("oauth_state")
    r.delete_cookie("user_email")
    return r
