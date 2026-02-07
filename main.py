"""
Gmail Cleaner Pro - FastAPI application for cleaning Gmail inbox.

This is the main application entry point. All business logic is modularized:
- config.py: Environment and OAuth configuration
- auth/: OAuth authentication flow
- services/: Gmail API interactions
- routes/: HTTP endpoints
- sessions/: User session management
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import routes
from routes.home import router as home_router
from routes.auth_routes import router as auth_router
from routes.progress import router as progress_router

# Initialize FastAPI app
app = FastAPI(title="Gmail Cleaner Pro", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(home_router)
app.include_router(auth_router)
app.include_router(progress_router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

