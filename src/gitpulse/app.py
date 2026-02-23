from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="GitPulse", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
	"""Serve the main dashboard page."""
	html_path = STATIC_DIR / "index.html"
	return HTMLResponse(content=html_path.read_text())
