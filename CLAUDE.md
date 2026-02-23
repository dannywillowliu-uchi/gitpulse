# GitPulse

GitHub project progress visualization dashboard. Paste any GitHub repo URL, get an interactive dashboard with commits, contributors, code hotspots, file structure, and more.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn, httpx (async)
- **Frontend**: Single self-contained HTML file with inline CSS/JS
- **Charts**: ECharts 5.5 (CDN) for standard charts, D3.js v7 (CDN) for force-directed/treemap
- **Styling**: Tailwind CSS (CDN), dark theme
- **No build step, no npm, no node**

## Project Structure

```
gitpulse/
├── pyproject.toml              # Project config, dependencies
├── CLAUDE.md                   # YOU ARE HERE - project instructions
├── mission-control.toml        # Mission control config
├── src/gitpulse/
│   ├── __init__.py
│   ├── app.py                  # FastAPI app, routes, serves frontend
│   ├── github_client.py        # Async GitHub REST API wrapper
│   ├── git_analyzer.py         # Local git clone analysis (subprocess)
│   ├── cache.py                # File-based JSON cache with TTL
│   └── static/
│       └── index.html          # Complete frontend dashboard (single file)
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (TestClient, temp repos)
│   ├── test_app.py             # Route/integration tests
│   ├── test_github_client.py   # GitHub client unit tests
│   ├── test_git_analyzer.py    # Git analyzer unit tests
│   └── test_cache.py           # Cache unit tests
```

## Coding Standards

- **Indentation**: Tabs (not spaces)
- **Quotes**: Double quotes
- **Line length**: 100 characters max
- **Type hints**: Use on all function signatures
- **Imports**: stdlib, then third-party, then local (isort compatible)
- **Docstrings**: Module-level and public functions only, keep brief
- **No unnecessary abstractions**: Keep it simple and direct
- **Error handling**: Only at boundaries (API endpoints, external calls)

## Verification

Run before every commit:

```bash
.venv/bin/python -m pytest -q && .venv/bin/ruff check src/ tests/
```

Setup (if .venv doesn't exist): `uv sync`

## API Endpoints

### GET /

Serves `static/index.html`.

### GET /api/analyze?repo_url={url}

Analyzes a GitHub repository. Accepts GitHub URLs in these formats:
- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `github.com/owner/repo`

**Response** (200 OK):

```json
{
	"repo": {
		"owner": "string",
		"name": "string",
		"url": "string"
	},
	"summary": {
		"total_commits": 0,
		"total_contributors": 0,
		"total_loc": 0,
		"open_prs": 0,
		"repo_age_days": 0,
		"most_active_file": "string"
	},
	"commit_activity": [
		{"week": 1700000000, "additions": 0, "deletions": 0}
	],
	"code_frequency": [
		{"week": 1700000000, "additions": 0, "deletions": 0}
	],
	"contributors": [
		{
			"login": "string",
			"avatar_url": "string",
			"total_commits": 0,
			"weeks": [{"week": 1700000000, "commits": 0, "additions": 0, "deletions": 0}]
		}
	],
	"punch_card": [
		{"day": 0, "hour": 0, "commits": 0}
	],
	"languages": {"Python": 50000, "JavaScript": 20000},
	"pulls": {
		"open": 0,
		"closed": 0,
		"merged": 0
	},
	"hotspots": [
		{"path": "string", "loc": 0, "changes": 0, "directory": "string"}
	],
	"file_tree": [
		{"path": "string", "loc": 0, "churn": 0, "children": []}
	],
	"survival_curves": [
		{
			"cohort": "2024-Q1",
			"data": [{"months_after": 0, "survival_pct": 100.0}]
		}
	]
}
```

**Error responses**:
- 400: Invalid repo URL format
- 404: Repository not found
- 502: GitHub API error

## GitHub REST API Reference

Base URL: `https://api.github.com/repos/{owner}/{repo}`

### Statistics Endpoints (202 Retry Pattern)

These endpoints return **202 Accepted** when GitHub is computing stats. You MUST retry with exponential backoff (1s, 2s, 4s) up to 5 times until you get 200.

| Endpoint | Returns |
|----------|---------|
| `/stats/commit_activity` | Weekly commit counts for last year |
| `/stats/code_frequency` | Weekly additions/deletions for repo lifetime |
| `/stats/contributors` | Per-contributor weekly commit/addition/deletion stats |
| `/stats/punch_card` | Commits by day-of-week and hour |

### Other Endpoints (No retry needed)

| Endpoint | Returns |
|----------|---------|
| `/languages` | Language byte counts |
| `/pulls?state=open&per_page=1` | Open PRs (check `Link` header for total count) |
| `/pulls?state=closed&per_page=1` | Closed PRs |

### Rate Limiting

- Unauthenticated: 60 requests/hour
- Authenticated (GITHUB_TOKEN env var): 5000 requests/hour
- Check `X-RateLimit-Remaining` header; if 0, wait until `X-RateLimit-Reset` timestamp

### Authentication

If `GITHUB_TOKEN` environment variable is set, include header:
```
Authorization: Bearer {token}
```

## github_client.py Implementation

```python
class GitHubClient:
	"""Async GitHub API client with 202 retry and rate limit handling."""

	BASE_URL = "https://api.github.com"

	def __init__(self, token: str | None = None):
		# Create httpx.AsyncClient with auth header if token provided
		# Set User-Agent header (required by GitHub)
		pass

	async def get_stats(self, owner: str, repo: str, stat: str) -> list | dict:
		# GET /repos/{owner}/{repo}/stats/{stat}
		# Retry on 202 with exponential backoff: 1s, 2s, 4s, 8s, 16s
		# Raise on rate limit (403 with X-RateLimit-Remaining: 0)
		pass

	async def get_languages(self, owner: str, repo: str) -> dict:
		pass

	async def get_pull_counts(self, owner: str, repo: str) -> dict:
		# Use per_page=1 and parse Link header for total count
		pass

	async def fetch_all(self, owner: str, repo: str) -> dict:
		# Gather all stats concurrently with asyncio.gather
		# Return combined dict matching API response schema
		pass

	async def close(self):
		pass
```

## git_analyzer.py Implementation

**Approach**: Use `subprocess.run` to call git commands. Clone as bare repo into temp directory. Parse command output directly.

```python
class GitAnalyzer:
	"""Analyze git repos via bare clone and subprocess commands."""

	async def analyze(self, repo_url: str) -> dict:
		# 1. Create temp dir
		# 2. Bare clone: git clone --bare {url} {temp_dir}/repo.git
		# 3. Run analysis functions
		# 4. Clean up temp dir
		# Return dict with hotspots, file_tree, survival_curves
		pass

	def _get_file_hotspots(self, repo_path: str) -> list[dict]:
		# git log --format=format: --name-only | sort | uniq -c | sort -rn
		# Returns [{path, changes}] sorted by change count desc
		pass

	def _get_file_tree(self, repo_path: str) -> list[dict]:
		# git ls-tree -r --name-only HEAD
		# For each file: wc -l via git show HEAD:{path} | wc -l
		# Build nested tree structure with LOC at each node
		pass

	def _get_code_churn(self, repo_path: str) -> dict:
		# git log --numstat --format=format:%H
		# Aggregate additions/deletions per file
		pass

	def _get_survival_curves(self, repo_path: str) -> list[dict]:
		# Group commits by quarter (YYYY-QN)
		# For each quarter cohort: git blame each file, count lines surviving from that quarter
		# Calculate survival percentage over time
		# This is the most complex analysis - prioritize correctness over performance
		pass
```

**Important**: Use `asyncio.to_thread` or `loop.run_in_executor` for subprocess calls to avoid blocking the event loop.

## cache.py Implementation

```python
CACHE_DIR = Path.home() / ".cache" / "gitpulse"

class Cache:
	"""File-based JSON cache with TTL."""

	def __init__(self, cache_dir: Path = CACHE_DIR, ttl_seconds: int = 3600):
		pass

	def _make_key(self, repo_url: str, head_sha: str) -> str:
		# SHA256(repo_url + head_sha) -> hex string
		pass

	def get(self, repo_url: str, head_sha: str) -> dict | None:
		# Look up cache file, check TTL, return parsed JSON or None
		pass

	def set(self, repo_url: str, head_sha: str, data: dict) -> None:
		# Atomic write: write to temp file, rename to cache path
		# Include timestamp in cached data for TTL checking
		pass
```

## Frontend Design

### CDN URLs

```html
<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>

<!-- ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>

<!-- D3.js -->
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
```

### Color Palette (Dark Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| bg-primary | #0d1117 | Page background |
| bg-card | #161b22 | Card backgrounds |
| bg-hover | #1c2128 | Hover states |
| border | #30363d | Card borders, dividers |
| text-primary | #e6edf3 | Main text |
| text-secondary | #8b949e | Muted text, labels |
| accent-blue | #58a6ff | Links, primary actions |
| accent-purple | #bc8cff | Secondary accent |
| accent-green | #3fb950 | Positive values, additions |
| accent-red | #f85149 | Negative values, deletions |
| accent-orange | #d29922 | Warnings, medium values |
| accent-cyan | #39d2c0 | Tertiary accent |

### Layout

- Max width: 1400px, centered
- Header: repo URL input + analyze button, sticky top
- KPI row: 6 cards in a grid (3x2 on mobile, 6x1 on desktop)
- Charts: 2-column grid on desktop, single column on mobile
- Each chart in a card with title, optional subtitle, border

### Chart Specifications

**1. Commit Timeline (ECharts)**
- Type: Stacked area chart
- X-axis: weeks (from code_frequency data)
- Y-axis: lines of code
- Series: additions (green), deletions (red, negative), net LOC (blue, toggleable)
- Tooltip: show week date + values

**2. Activity Heatmap (ECharts)**
- Type: Heatmap (7 rows x 24 columns)
- Y-axis: days (Mon-Sun)
- X-axis: hours (0-23)
- Color: bg-primary (0 commits) -> accent-green (max commits)
- Data from punch_card endpoint

**3. Contributor Sparkline Table**
- HTML table with ECharts mini line charts (80x30px) per row
- Columns: avatar (32px circle), login, total commits, sparkline (last 52 weeks)
- Sorted by total commits desc
- Max 20 rows, "show all" toggle if more

**4. Language Donut (ECharts)**
- Type: Pie/donut chart
- Inner radius: 60%, outer radius: 80%
- Label: language name + percentage
- Center text: total LOC
- Colors: cycle through accent palette

**5. Hotspot Bubble Map (D3.js)**
- Type: Force-directed bubble chart
- Each bubble = one file
- Size = LOC (radius scaled sqrt)
- Color = change frequency (green -> orange -> red gradient)
- Grouped by top-level directory (force clusters)
- Hover tooltip: file path, LOC, change count
- Simulation: d3.forceSimulation with forceX/forceY per directory cluster

**6. File Treemap (D3.js)**
- Type: Zoomable treemap
- Area = LOC
- Color = churn intensity (same green -> red gradient)
- Click directory to zoom in, breadcrumb to zoom out
- Labels: file/dir name, truncated if small
- Use d3.treemap() layout

**7. Code Survival Curves (ECharts)**
- Type: Multi-line chart
- X-axis: months after cohort quarter
- Y-axis: survival percentage (0-100%)
- One line per quarter cohort
- Colors: gradient from old (muted) to recent (bright)
- Legend: quarter labels

### Loading States

- Initial: Show URL input centered with example repo chips below
- Loading: Skeleton cards with pulse animation, progress text
- Error: Red-bordered card with error message and retry button
- Success: Fade-in charts with staggered animation

### Example Repo Chips

Clickable chips that pre-fill the URL input:
- `facebook/react`
- `torvalds/linux`
- `fastapi/fastapi`
- `donnemartin/system-design-primer`

## app.py Wiring

```python
@app.get("/api/analyze")
async def analyze(repo_url: str) -> dict:
	# 1. Parse and validate repo URL -> owner, repo
	# 2. Check cache (need HEAD SHA first - quick API call)
	# 3. If cache hit, return cached data
	# 4. Fetch GitHub API data via GitHubClient
	# 5. Run git analysis via GitAnalyzer
	# 6. Merge results into response schema
	# 7. Cache the result
	# 8. Return response
	pass
```

Parse repo URL with regex: `(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/.]+)(?:\.git)?`

## Testing Guidelines

- Use `pytest` with `pytest-asyncio` for async tests
- Mock HTTP calls with `httpx.MockTransport` or `respx`
- For git_analyzer tests: create real temp bare repos with known commit history
- Test the 202 retry loop with mock responses
- Test cache TTL expiry
- Test URL parsing edge cases
- Frontend is not unit tested (manual verification)

## Common Gotchas

1. **GitHub 202 responses**: Stats endpoints return 202 while computing. MUST retry.
2. **Rate limiting**: Always check headers. Unauthenticated = 60 req/hr.
3. **Bare clone paths**: Use `repo.git` convention inside temp dirs.
4. **Large repos**: Set timeout on git clone (60s max). Skip survival curves if >10k commits.
5. **Empty repos**: Handle repos with 0 commits gracefully.
6. **subprocess in async**: Always use `asyncio.to_thread` or `run_in_executor`.
7. **Ruff compliance**: Run `ruff check` before committing. Fix all issues.
8. **Tab indentation**: The project uses tabs. Configure editors accordingly.
