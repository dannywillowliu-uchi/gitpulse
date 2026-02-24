import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from gitpulse.cache import Cache
from gitpulse.github_client import GitHubClient

logger = logging.getLogger(__name__)

try:
	from gitpulse.git_analyzer import (
		get_churn,
		get_file_tree,
		get_hotspots,
		get_survival_curves,
	)
except ImportError:
	get_hotspots = None
	get_file_tree = None
	get_churn = None
	get_survival_curves = None

app = FastAPI(title="GitPulse", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
REPO_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$")
cache = Cache()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
	"""Serve the main dashboard page."""
	html_path = STATIC_DIR / "index.html"
	return HTMLResponse(content=html_path.read_text())


@app.get("/api/health")
async def health() -> dict:
	return {"status": "ok"}


@app.get("/api/analyze", response_model=None)
async def analyze(repo: str = Query(...)) -> dict | JSONResponse:
	if not REPO_PATTERN.match(repo):
		return JSONResponse(
			status_code=400,
			content={"detail": "Invalid repo format. Use owner/repo."},
		)

	owner, repo_name = repo.split("/", 1)
	repo_url = f"https://github.com/{owner}/{repo_name}"

	try:
		async with GitHubClient() as client:
			repo_meta = await client.get_repo(owner, repo_name)
			head_sha = repo_meta.get("pushed_at", "unknown")

			cached = cache.get(repo, head_sha)
			if cached is not None:
				return cached

			(
				commit_activity_raw,
				code_frequency_raw,
				contributors_raw,
				punch_card_raw,
				open_pulls,
				languages,
			) = await asyncio.gather(
				client.get_commit_activity(owner, repo_name),
				client.get_code_frequency(owner, repo_name),
				client.get_contributors(owner, repo_name),
				client.get_punch_card(owner, repo_name),
				client.get_open_pulls(owner, repo_name),
				client.get_languages(owner, repo_name),
			)

		if get_hotspots is not None:
			hotspots, file_tree_raw, churn_data, survival_curves = await asyncio.gather(
				get_hotspots(repo_url),
				get_file_tree(repo_url),
				get_churn(repo_url),
				get_survival_curves(repo_url),
			)
			churn_by_path = churn_data if isinstance(churn_data, dict) else {}
			file_tree = [
				{
					"path": f["path"],
					"loc": f["loc"],
					"churn": churn_by_path.get(f["path"], 0),
				}
				for f in file_tree_raw
			]
		else:
			hotspots = []
			file_tree = []
			survival_curves = []

		commit_activity = [
			{
				"week": entry[0],
				"additions": entry[1],
				"deletions": abs(entry[2]),
			}
			for entry in (code_frequency_raw or [])
		]

		punch_card = [
			{"day": entry[0], "hour": entry[1], "commits": entry[2]}
			for entry in (punch_card_raw or [])
		]

		contributors = [
			{
				"login": c["author"]["login"],
				"avatar_url": c["author"]["avatar_url"],
				"total_commits": c["total"],
				"weekly_commits": [w["c"] for w in c["weeks"]],
			}
			for c in (contributors_raw or [])
			if c.get("author") is not None
		]

		total_commits = sum(w["total"] for w in (commit_activity_raw or []))
		loc = sum((languages or {}).values())
		created_at = repo_meta.get("created_at", "")
		if created_at:
			created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
			repo_age_days = (datetime.now(timezone.utc) - created_dt).days
		else:
			repo_age_days = 0

		most_active_file = hotspots[0]["path"] if hotspots else ""

		result = {
			"repo": repo,
			"analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
			"summary": {
				"total_commits": total_commits,
				"contributors": len(contributors),
				"loc": loc,
				"open_prs": len(open_pulls or []),
				"repo_age_days": repo_age_days,
				"most_active_file": most_active_file,
			},
			"commit_activity": commit_activity,
			"punch_card": punch_card,
			"contributors": contributors,
			"languages": languages or {},
			"hotspots": hotspots,
			"file_tree": file_tree,
			"survival_curves": survival_curves,
		}

		cache.set(repo, head_sha, result)
		return result

	except httpx.HTTPStatusError as exc:
		if exc.response.status_code == 404:
			return JSONResponse(
				status_code=404,
				content={"detail": "Repository not found."},
			)
		return JSONResponse(
			status_code=502,
			content={"detail": "GitHub API error."},
		)
	except (TimeoutError, httpx.HTTPError):
		return JSONResponse(
			status_code=502,
			content={"detail": "GitHub API error."},
		)
