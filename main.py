from fastapi import FastAPI, Form, Request, Response, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os, asyncio, json

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
REDIRECT_URI = os.environ.get("REDIRECT_URI")
client_config = json.loads(os.environ.get("GOOGLE_CLIENT_CONFIG_JSON"))

# ---------------- HOME PAGE ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>Gmail Cleaner</title>
        <style>
            body { font-family: 'Segoe UI'; background:#eef2f7; text-align:center; padding:40px;}
            .card { background:white; padding:30px; border-radius:12px; width:430px; margin:auto; box-shadow:0 10px 25px rgba(0,0,0,0.1);}
            h2 { color:#333 }
            label { display:block; margin:10px 0; text-align:left;}
            button { padding:12px; width:100%; background:#4285F4; color:white; border:none; border-radius:8px; font-size:16px;}
            select { width:100%; padding:8px; border-radius:6px;}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🧹 Gmail Smart Cleaner</h2>
            <form action="/start" method="post">
                <label><input type="checkbox" name="unread" checked> Unread</label>
                <label><input type="checkbox" name="promotions" checked> Promotions</label>
                <label><input type="checkbox" name="social"> Social</label>
                <label><input type="checkbox" name="updates"> Updates</label>

                <label>Delete emails older than:</label>
                <select name="age">
                    <option value="">No filter</option>
                    <option value="7d">1 Week</option>
                    <option value="1m">1 Month</option>
                    <option value="1y">1 Year</option>
                </select>
                <br><br>
                <button type="submit">Login & Clean</button>
            </form>
        </div>
    </body>
    </html>
    """

# ---------------- START LOGIN ----------------
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

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, state = flow.authorization_url(prompt='consent')

    response = RedirectResponse(auth_url)
    response.set_cookie("oauth_state", state, httponly=True, secure=True, samesite="Lax")
    response.set_cookie("clean_queries", ",".join(queries), httponly=True, secure=True, samesite="Lax")
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

    response = RedirectResponse("/progress_page")
    response.set_cookie("user_token", creds.to_json(), httponly=True, secure=True, samesite="Lax")
    response.set_cookie("user_email", email, secure=True, samesite="Lax")
    return response

# ---------------- PROGRESS UI ----------------
@app.get("/progress_page", response_class=HTMLResponse)
def progress_page(user_email: str = Cookie("")):
    return f"""
    <html>
    <head>
        <title>Cleaning...</title>
        <style>
            body {{ font-family: 'Segoe UI'; background:#eef2f7; text-align:center; padding:40px;}}
            .card {{ background:white; padding:30px; border-radius:12px; width:520px; margin:auto; box-shadow:0 10px 25px rgba(0,0,0,0.1);}}
            #barWrap {{ background:#ddd;height:20px;border-radius:10px;margin-top:20px;}}
            #bar {{ height:20px;width:0%;background:#34A853;border-radius:10px;}}
            ul {{ text-align:left; max-height:200px; overflow:auto; }}
            .email {{ font-size:14px; color:#666 }}
            .logout {{ margin-top:15px; display:inline-block; color:#4285F4; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Cleaning Gmail Inbox</h2>
            <div class="email">Logged in as: <b>{user_email}</b></div>
            <div id="barWrap"><div id="bar"></div></div>
            <p id="status">Starting...</p>
            <ul id="log"></ul>
            <a href="/logout" class="logout">Logout</a>
        </div>

        <script>
            var source = new EventSource("/progress");
            let percent = 0;
            source.onmessage = function(event){{
                let msg = event.data;
                document.getElementById("status").innerText = msg;
                document.getElementById("log").innerHTML += "<li>"+msg+"</li>";
                percent += 5;
                document.getElementById("bar").style.width = Math.min(percent,100)+"%";
                if(msg.includes("DONE") || msg.includes("No matching")) {{
                    source.close();
                    document.getElementById("bar").style.width = "100%";
                }}
            }};
        </script>
    </body>
    </html>
    """

# ---------------- CLEANING STREAM ----------------
@app.get("/progress")
async def progress(user_token: str = Cookie(None), clean_queries: str = Cookie("")):

    async def event_stream():
        creds = Credentials.from_authorized_user_info(json.loads(user_token))
        service = build('gmail', 'v1', credentials=creds)
        queries = clean_queries.split(",") if clean_queries else []

        total_deleted = 0
        found_any = False
        yield "data: Starting cleanup...\n\n"

        for query in queries:
            next_page_token = None
            while True:
                results = service.users().messages().list(userId='me', q=query, maxResults=500, pageToken=next_page_token).execute()
                messages = results.get('messages', [])
                if not messages: break
                found_any = True
                ids = [m['id'] for m in messages]
                service.users().messages().batchModify(userId='me', body={'ids': ids, 'addLabelIds': ['TRASH']}).execute()
                total_deleted += len(ids)
                yield f"data: Deleted {total_deleted} emails...\n\n"
                await asyncio.sleep(0.2)
                next_page_token = results.get('nextPageToken')
                if not next_page_token: break

        if not found_any:
            yield "data: No matching emails found 🎉\n\n"
        else:
            yield f"data: DONE. Total deleted: {total_deleted}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ---------------- LOGOUT ----------------
@app.get("/logout")
def logout():
    response = RedirectResponse("/")
    response.delete_cookie("user_token")
    response.delete_cookie("oauth_state")
    response.delete_cookie("clean_queries")
    response.delete_cookie("user_email")
    return response
