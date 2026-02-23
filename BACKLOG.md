## P0: Backend Data Layer (github_client, cache, /api/analyze endpoint)

Build github_client.py as an async httpx wrapper with 202 retry pattern and rate limit handling.
Build cache.py as file-based JSON cache with SHA256 key, ~/.cache/gitpulse/ storage, 1hr TTL, and atomic writes.
Wire /api/analyze endpoint in app.py that parses repo URL, calls GitHubClient.fetch_all(), caches results, and returns the full response schema from CLAUDE.md.
Leave git analysis fields (hotspots, file_tree, survival_curves) as empty lists.
Add /api/health endpoint returning {"status": "ok"}.
Write comprehensive tests for all three modules: test_github_client.py (mock httpx, test 202 retry, rate limits), test_cache.py (tmp_path, TTL expiry, atomic writes), test_app.py (mock GitHubClient, test /api/analyze and error responses).
GITHUB_TOKEN env var support for authentication (optional, increases rate limit).
Read CLAUDE.md for complete API schemas and implementation details.

## P1: Git Clone Analysis (git_analyzer, integrate into /api/analyze)

Build git_analyzer.py using subprocess (not gitpython) with bare clones into temp directories.
Implement file hotspots (change frequency per file via git log --name-only).
Implement file tree with LOC (git ls-tree + line counting).
Implement code churn per file (git log --numstat, sum additions/deletions).
Implement code survival curves (quarter cohorts, git blame sampling at 4-week intervals, cap at 8 cohorts).
Use asyncio.to_thread for subprocess calls to avoid blocking the event loop.
All subprocess calls must have timeout=60, capture stderr, check returncode.
Integrate into /api/analyze endpoint: call GitAnalyzer after GitHubClient, merge results.
Write tests with real temp bare repos (create commits programmatically, verify analysis output).
Clean up temp directories in finally blocks.
Read CLAUDE.md for exact git commands and survival curve algorithm.

## P2: Frontend Dashboard (index.html with ECharts and D3.js)

Build complete index.html as a single self-contained file with inline CSS/JS.
CDN dependencies: ECharts 5.x, D3.js v7, Tailwind CSS.
URL input bar with analyze button, parse github.com URLs and owner/repo format.
Loading states: skeleton cards with pulse animation, "Analyzing {repo}..." text.
6 KPI cards: total commits, contributors, LOC, open PRs, repo age, most active file. Animate counters on load.
Commit timeline: ECharts stacked area (additions green, deletions red, toggleable net LOC).
Activity heatmap: ECharts 7x24 grid (day x hour), gradient from bg-card to accent-blue.
Contributor sparkline table: HTML table with 80x24px inline ECharts sparklines per row.
Language donut: ECharts pie with radius ["40%", "70%"], center text showing total LOC.
Hotspot bubble map: D3 force-directed, bubble size=LOC, color=change frequency, grouped by directory.
File treemap: D3 nested rectangles, area=LOC, color=churn intensity, click-to-zoom with breadcrumbs.
Code survival curves: ECharts line chart, one series per quarter-cohort.
Dark theme using color palette from CLAUDE.md. Layout follows the diagram in CLAUDE.md.
Tailwind config with gp-* custom colors.
Error states: red-bordered card with message and retry button.
Read CLAUDE.md for exact color hex codes, CDN URLs, layout spec, and chart details.

## P3: Polish and Hardening (error handling, UX, integration tests)

Error handling: exponential backoff on GitHub API failures, request timeouts, corrupted cache recovery (delete and re-fetch), graceful handling of empty repos (0 commits).
Frontend polish: example repo chips (facebook/react, torvalds/linux, fastapi/fastapi) that pre-fill input, fade-in animations on chart load with staggered timing, empty state messages for missing data sections, mobile-responsive layout.
Integration tests: end-to-end test with mocked GitHub API that exercises full /api/analyze flow, test with various repo sizes and edge cases.
README.md with project description, screenshot placeholder, setup instructions (uv sync, uvicorn), usage, and tech stack.
