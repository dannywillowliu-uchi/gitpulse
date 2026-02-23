# GitPulse

GitHub project progress visualization dashboard. Paste any GitHub repo URL, get an interactive dashboard with commits, contributors, code hotspots, file structure, and more.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, uvicorn, httpx (async)
- **Frontend**: Single self-contained HTML file with inline CSS/JS
- **Charts**: ECharts 5.x via CDN (standard charts), D3.js v7 via CDN (force-directed, treemap)
- **Styling**: Tailwind CSS via CDN
- **No build step, no npm, no node**

## Project Structure

```
gitpulse/
├── pyproject.toml              # Project config and dependencies
├── CLAUDE.md                   # THIS FILE -- project instructions for all workers
├── mission-control.toml        # Mission control config
├── src/gitpulse/
│   ├── __init__.py
│   ├── app.py                  # FastAPI application, routes, serves frontend
│   ├── github_client.py        # Async GitHub REST API client
│   ├── git_analyzer.py         # Local git clone analysis (subprocess-based)
│   ├── cache.py                # File-based JSON cache with TTL
│   └── static/
│       └── index.html          # Complete frontend dashboard (single file)
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures (TestClient, temp repos)
│   ├── test_app.py             # Route/integration tests
│   ├── test_github_client.py   # GitHub client tests (mock httpx)
│   ├── test_git_analyzer.py    # Git analyzer tests (temp bare repos)
│   └── test_cache.py           # Cache tests (tmp_path)
```

## Coding Standards

- **Indentation**: Tabs (enforced by ruff)
- **Quotes**: Double quotes
- **Line length**: 100 characters max
- **Type hints**: Use on all function signatures
- **Comments**: Minimal, only when logic is non-obvious
- **Imports**: sorted by ruff (isort compatible)
- **Async**: All I/O-bound functions must be async

## Verification Command

```bash
.venv/bin/python -m pytest -q && .venv/bin/ruff check src/ tests/
```

Run this before every commit. Both must pass.

## API Endpoints

### `GET /`

Serves `static/index.html`. No parameters.

### `GET /api/analyze?repo={owner/repo}`

Main analysis endpoint. Accepts GitHub repo in `owner/repo` format.

**Response schema** (200 OK):

```json
{
  "repo": "owner/repo",
  "analyzed_at": "2025-01-15T10:30:00Z",
  "summary": {
    "total_commits": 1234,
    "contributors": 15,
    "loc": 45000,
    "open_prs": 3,
    "repo_age_days": 730,
    "most_active_file": "src/main.py"
  },
  "commit_activity": [
    {"week": 1704067200, "additions": 500, "deletions": 120}
  ],
  "punch_card": [
    {"day": 0, "hour": 14, "commits": 5}
  ],
  "contributors": [
    {
      "login": "user1",
      "avatar_url": "https://...",
      "total_commits": 200,
      "weekly_commits": [0, 3, 5, 2, 8, 1, 0]
    }
  ],
  "languages": {
    "Python": 35000,
    "JavaScript": 8000,
    "HTML": 2000
  },
  "hotspots": [
    {"path": "src/main.py", "loc": 450, "change_count": 87, "directory": "src"}
  ],
  "file_tree": [
    {"path": "src/main.py", "loc": 450, "churn": 120}
  ],
  "survival_curves": [
    {
      "cohort": "2024-Q1",
      "data": [
        {"weeks_elapsed": 0, "surviving_lines": 1.0},
        {"weeks_elapsed": 4, "surviving_lines": 0.92}
      ]
    }
  ]
}
```

**Error responses**:
- `400`: Invalid repo format
- `404`: Repo not found on GitHub
- `502`: GitHub API error

### `GET /api/health`

Returns `{"status": "ok"}`.

## GitHub REST API Reference

Base URL: `https://api.github.com`

Authentication: `Authorization: Bearer {GITHUB_TOKEN}` header (from env var, optional but recommended for rate limits).

### Endpoints Used

| Endpoint | Returns |
|----------|---------|
| `GET /repos/{owner}/{repo}` | Repo metadata (created_at, default_branch) |
| `GET /repos/{owner}/{repo}/stats/commit_activity` | Weekly commit counts (52 weeks) |
| `GET /repos/{owner}/{repo}/stats/code_frequency` | Weekly additions/deletions |
| `GET /repos/{owner}/{repo}/stats/contributors` | Per-contributor weekly commit data |
| `GET /repos/{owner}/{repo}/stats/punch_card` | Day x hour commit counts |
| `GET /repos/{owner}/{repo}/pulls?state=open` | Open pull requests |
| `GET /repos/{owner}/{repo}/languages` | Language byte counts |

### 202 Retry Pattern

GitHub statistics endpoints return **202 Accepted** when data is being computed. Implementation:

```python
async def fetch_with_retry(client: httpx.AsyncClient, url: str) -> dict:
    for attempt in range(5):
        response = await client.get(url)
        if response.status_code == 200:
            return response.json()
        if response.status_code == 202:
            await asyncio.sleep(2 ** attempt)  # 1, 2, 4, 8, 16 seconds
            continue
        response.raise_for_status()
    raise TimeoutError(f"GitHub still computing stats after retries: {url}")
```

### Rate Limit Handling

Check `X-RateLimit-Remaining` header. If 0, read `X-RateLimit-Reset` (Unix timestamp) and sleep until reset. Log a warning when remaining < 10.

## Git Analysis Approach

### Critical Rules

- **Use `subprocess.run`** (or `asyncio.create_subprocess_exec`), NOT gitpython
- **Bare clone**: `git clone --bare {url} {temp_dir}` -- faster, no working tree
- **Temp directories**: Use `tempfile.mkdtemp()`, clean up in `finally` block
- **All subprocess calls**: Set `timeout=60`, capture stderr, check returncode

### File Hotspots

```bash
git -C {bare_repo} log --format="" --name-only | sort | uniq -c | sort -rn
```

Count how many commits touched each file. Returns list of `(path, change_count)`.

### File Tree with LOC

From the bare repo, list all blobs at HEAD and count lines:

```bash
git -C {bare_repo} ls-tree -r --name-only HEAD
git -C {bare_repo} cat-file -p {blob_sha}  # count newlines
```

Or more efficiently, use `git diff --stat` against empty tree:

```bash
git -C {bare_repo} diff --stat $(git hash-object -t tree /dev/null) HEAD
```

### Code Churn Per File

```bash
git -C {bare_repo} log --numstat --format=""
```

Parse output: each line is `additions\tdeletions\tfilepath`. Sum per file.

### Code Survival Curves

For each quarter-cohort:
1. Find all commits in that quarter
2. For each commit, get the added lines (`git log -p --diff-filter=A`)
3. Use `git blame` at subsequent points in time to check how many of those lines still exist
4. Calculate survival rate = surviving_lines / original_lines

Simplified approach using `git log --follow` and `git blame`:

```bash
# Get lines added in Q1 2024 (commits from that quarter)
git -C {bare_repo} log --after="2024-01-01" --before="2024-04-01" --format="%H"

# For each subsequent quarter-end, blame the file and count matching lines
git -C {bare_repo} blame --porcelain {rev} -- {file}
```

Group by quarter, sample survival at 4-week intervals. Cap at 8 cohorts (2 years).

## Cache Design

### Key Generation

```python
import hashlib
cache_key = hashlib.sha256(f"{repo_url}:{head_sha}".encode()).hexdigest()
```

### Storage

- Location: `~/.cache/gitpulse/`
- Files: `{cache_key}.json`
- TTL: 1 hour (3600 seconds)
- Check: Compare file mtime against `time.time() - 3600`

### Atomic Writes

Write to `{cache_key}.tmp`, then `os.rename()` to `{cache_key}.json`. This prevents partial reads.

### Cache Flow

1. Parse repo URL to `owner/repo`
2. Fetch HEAD SHA from GitHub API (`GET /repos/{owner}/{repo}` -> `default_branch`, then resolve)
3. Compute cache key from `owner/repo:HEAD_SHA`
4. If cache hit (file exists, mtime < 1hr): return cached JSON
5. If cache miss: fetch all data, write cache, return

## Frontend Design

### CDN URLs

```html
<!-- ECharts -->
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>

<!-- D3.js -->
<script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>

<!-- Tailwind CSS -->
<script src="https://cdn.tailwindcss.com"></script>
```

### Color Palette (Dark Theme)

| Token | Hex | Usage |
|-------|-----|-------|
| bg-primary | `#0d1117` | Page background |
| bg-card | `#161b22` | Card/panel background |
| bg-input | `#21262d` | Input fields |
| border | `#30363d` | Borders, dividers |
| text-primary | `#e6edf3` | Main text |
| text-secondary | `#8b949e` | Muted text, labels |
| accent-blue | `#58a6ff` | Links, primary actions |
| accent-purple | `#bc8cff` | Secondary accent |
| accent-green | `#3fb950` | Success, additions |
| accent-red | `#f85149` | Error, deletions |
| accent-orange | `#d29922` | Warnings |
| accent-cyan | `#39d2c0` | Tertiary accent |

### Layout

```
┌─────────────────────────────────────────────────┐
│  GitPulse          [repo URL input] [Analyze]   │
├─────────────────────────────────────────────────┤
│  KPI1  │  KPI2  │  KPI3  │  KPI4  │  KPI5  │K6│  <- 6 KPI cards in a row
├─────────────────────────────────────────────────┤
│  Commit Timeline (stacked area)                 │  <- full width
├──────────────────────┬──────────────────────────┤
│  Activity Heatmap    │  Language Donut           │  <- 60/40 split
├──────────────────────┴──────────────────────────┤
│  Contributor Sparkline Table                    │  <- full width
├──────────────────────┬──────────────────────────┤
│  Hotspot Bubble Map  │  File Treemap            │  <- 50/50 split
├──────────────────────┴──────────────────────────┤
│  Code Survival Curves                           │  <- full width
└─────────────────────────────────────────────────┘
```

### Tailwind Config

```javascript
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "gp-bg": "#0d1117",
        "gp-card": "#161b22",
        "gp-input": "#21262d",
        "gp-border": "#30363d",
        "gp-text": "#e6edf3",
        "gp-muted": "#8b949e",
        "gp-blue": "#58a6ff",
        "gp-purple": "#bc8cff",
        "gp-green": "#3fb950",
        "gp-red": "#f85149",
        "gp-orange": "#d29922",
        "gp-cyan": "#39d2c0",
      }
    }
  }
}
```

### Chart Implementation Details

#### 1. Summary KPIs
Six cards in a flex row. Each card: icon (SVG or emoji-free unicode), value (large font), label (muted). Animate numbers counting up on load.

#### 2. Commit Timeline (ECharts)
- Type: Stacked area chart
- X-axis: weeks (from `commit_activity`)
- Series: additions (green), deletions (red)
- Toggle button for net LOC line overlay
- Tooltip: week date, additions, deletions, net

#### 3. Activity Heatmap (ECharts)
- Type: Heatmap (`echarts` calendar-style or custom grid)
- X-axis: hours (0-23), Y-axis: days (Sun-Sat)
- Data: `punch_card` array
- Color: gradient from bg-card to accent-blue (low to high)
- Tooltip: day name, hour, commit count

#### 4. Contributor Sparkline Table
- HTML table with ECharts mini line charts embedded in cells
- Columns: avatar, login, total commits, sparkline (last 52 weeks), % of total
- Sort by total commits descending
- Sparkline: 80x24px inline ECharts, accent-blue line, no axes

#### 5. Language Donut (ECharts)
- Type: Pie chart with `radius: ["40%", "70%"]` for donut
- Colors: cycle through accent palette
- Center text: total LOC
- Tooltip: language name, bytes, percentage

#### 6. Hotspot Bubble Map (D3)
- Type: Force-directed bubble chart
- Bubble size: proportional to LOC
- Bubble color: gradient based on change frequency (low=blue, high=red)
- Group by top-level directory (force clusters)
- Tooltip: file path, LOC, change count
- Collision detection to prevent overlap

#### 7. File Treemap (D3)
- Type: Nested rectangles (`d3.treemap()`)
- Area: proportional to LOC
- Color: churn intensity (low=green, high=red)
- Click-to-zoom into subdirectories
- Breadcrumb trail for navigation
- Tooltip: path, LOC, churn count

#### 8. Code Survival Curves (ECharts)
- Type: Line chart
- X-axis: weeks elapsed since cohort start
- Y-axis: percentage of lines surviving (0-100%)
- One series per quarter-cohort (different colors)
- Legend: cohort labels (e.g., "2024-Q1")
- Tooltip: cohort, weeks elapsed, survival %

### Frontend Flow

1. User pastes repo URL (e.g., `https://github.com/owner/repo`) or `owner/repo`
2. Parse to `owner/repo` format (strip github.com prefix if present)
3. Show loading skeleton (pulsing placeholder cards)
4. `fetch("/api/analyze?repo=owner/repo")`
5. On success: populate all charts, animate KPI counters
6. On error: show error banner with message, keep input enabled

### Loading States

- Skeleton cards with pulsing animation while waiting
- Progress text: "Analyzing {owner/repo}..."
- Individual chart placeholders that fill in as data arrives (single request, but stagger animations)

## Worker Guidelines

- **One module per worker** when possible. Don't touch files outside your assignment.
- **Always run verification** before marking work complete.
- **Tests go in separate files** matching `test_{module}.py`.
- **Mock external calls** in tests (httpx for GitHub, subprocess for git).
- **No global state**. Pass dependencies as function arguments.
- **Error handling**: Raise specific exceptions, don't catch-and-silence.
- **Logging**: Use `logging.getLogger(__name__)`, not print().
