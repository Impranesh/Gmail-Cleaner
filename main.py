from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse, StreamingResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os, asyncio, json

# load .env when present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

app = FastAPI()

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Build OAuth flow from environment-configured client info if available.
# Prefer a full JSON client config in the env var `GOOGLE_CLIENT_CONFIG_JSON`.
client_config_json = os.environ.get("GOOGLE_CLIENT_CONFIG_JSON")
redirect_uri = os.environ.get("REDIRECT_URI", 'http://localhost:8000/auth/callback')

if client_config_json:
    try:
        client_config = json.loads(client_config_json)
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
    except Exception:
        # fallback to client secrets file if JSON is invalid
        flow = Flow.from_client_secrets_file(
            os.environ.get('CLIENT_SECRETS_FILE', 'cred_web.json'),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
else:
    flow = Flow.from_client_secrets_file(
        os.environ.get('CLIENT_SECRETS_FILE', 'cred_web.json'),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

# ---------------- HOME PAGE ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
    <head>
        <title>Gmail Cleaner</title>
        <style>
            body { font-family: Arial; text-align:center; padding:40px; background:#f4f6f9; }
            .box { background:white; padding:30px; border-radius:10px; width:420px; margin:auto; box-shadow:0 0 10px rgba(0,0,0,0.1); }
            h2 { margin-bottom:20px; }
            button { padding:10px 20px; background:#4285F4; color:white; border:none; border-radius:5px; cursor:pointer; }
            label { display:block; margin:10px 0; text-align:left; }
            select { width:100%; padding:5px; }
        </style>
    </head>
    <body>
        <div class="box">
            <h2>Gmail Cleaner</h2>
            <form action="/start" method="post">
                <label><input type="checkbox" name="unread" checked> Delete Unread</label>
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
                <br>
                <button type="submit">Login & Clean</button>
            </form>
        </div>
    </body>
    </html>
    """

# ---------------- START CLEANING ----------------
@app.post("/start")
def start(unread: str = Form(None), promotions: str = Form(None),
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

    auth_url, _ = flow.authorization_url(prompt='consent')
    return RedirectResponse(auth_url)

# ---------------- CALLBACK ----------------
@app.get("/auth/callback")
def callback(request: Request):
    flow.fetch_token(authorization_response=str(request.url))
    return RedirectResponse("/progress_page")

# ---------------- PROGRESS PAGE ----------------
@app.get("/progress_page", response_class=HTMLResponse)
def progress_page():
    return """
    <html>
    <head>
        <title>Cleaning...</title>
        <style>
            body { font-family: Arial; text-align:center; padding:40px; background:#f4f6f9; }
            .box { background:white; padding:30px; border-radius:10px; width:500px; margin:auto; box-shadow:0 0 10px rgba(0,0,0,0.1); }
            #barWrap { background:#ddd;width:100%;height:20px;border-radius:10px;margin-top:20px; }
            #bar { height:20px;width:0%;background:#4285F4;border-radius:10px; }
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

# ---------------- STREAM CLEANING PROGRESS ----------------
@app.get("/progress")
async def progress():
    async def event_stream():
        creds = flow.credentials
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
