"""
Home page route - displays the main UI for email cleaning.
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter()

# Template path
template_path = Path(__file__).parent.parent / "templates" / "home.html"


@router.get("/")
def home():
    """Display the home page."""
    return FileResponse(template_path)
