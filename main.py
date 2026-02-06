from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from google_auth_oauthlib.flow import Flow
import os, json, secrets

from routes import preview

app = FastAPI()
app.include_router(preview.router)

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
client_config = json.loads(os.environ["GOOGLE_CLIENT_CONFIG_JSON"])
REDIRECT_URI = os.environ["REDIRECT_URI"]

app.state.SESSIONS = {}

# ---------- HOME ----------
@app.get("/", response_class=HTMLResponse)
def home():
    return open("templates/home.html").read()

# ---------- START OAUTH ----------
@app.post("/start")
def start(unread: str = Form(None), promotions: str = Form(None),
          social: str = Form(None), updates: str = Form(None),
          age: str = Form("")):

    queries = []
    if unread: queries.append("is:unread")
    if promotions: queries.append("category:promotions")
    if social: queries.append("category:social")
    if updates: queries.append("category:updates")

    if age:
        queries = [q + f" older_than:{age}" for q in queries]

    session_id = secrets.token_hex(16)
    app.state.SESSIONS[session_id] = {"queries": queries}

    flow = Flow.from_client_config(client_config, SCOPES, redirect_uri=REDIRECT_URI)
    auth_url, state = flow.authorization_url(prompt='consent')
    app.state.SESSIONS[session_id]["state"] = state

    response = RedirectResponse(auth_url)
    response.set_cookie("session_id", session_id, httponly=True)
    return response

# ---------- CALLBACK ----------
@app.get("/auth/callback")
def callback(request: Request):
    session_id = request.cookies.get("session_id")
    session = app.state.SESSIONS.get(session_id)

    flow = Flow.from_client_config(client_config, SCOPES,
                                   state=session["state"], redirect_uri=REDIRECT_URI)
    flow.fetch_token(authorization_response=str(request.url))

    session["creds"] = flow.credentials.to_json()
    return RedirectResponse(f"/preview?query={session['queries'][0]}")
