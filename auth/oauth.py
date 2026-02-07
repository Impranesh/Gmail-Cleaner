"""
OAuth2 authentication module - handles Google OAuth flow.
"""
from google_auth_oauthlib.flow import Flow
from config import GOOGLE_CLIENT_CONFIG, SCOPES, REDIRECT_URI


def create_flow(state: str = None) -> Flow:
    """Create and return a Google OAuth flow."""
    flow = Flow.from_client_config(
        GOOGLE_CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state
    )
    return flow


def get_authorization_url() -> tuple:
    """Get the authorization URL for the user to visit."""
    flow = create_flow()
    auth_url, state = flow.authorization_url(prompt='consent')
    return auth_url, state


def get_credentials_from_callback(callback_url: str, state: str):
    """Exchange authorization code for credentials."""
    flow = create_flow(state=state)
    flow.fetch_token(authorization_response=callback_url)
    return flow.credentials
