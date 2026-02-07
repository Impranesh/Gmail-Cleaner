"""
Configuration module - loads and manages environment variables.
"""
import os
import json

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# OAuth2 config
GOOGLE_CLIENT_CONFIG = json.loads(os.environ.get("GOOGLE_CLIENT_CONFIG_JSON", "{}"))
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:8000/auth/callback")

# Ensure insecure transport for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Validation
if not GOOGLE_CLIENT_CONFIG:
    raise ValueError("GOOGLE_CLIENT_CONFIG_JSON environment variable not set")
if not REDIRECT_URI:
    raise ValueError("REDIRECT_URI environment variable not set")
