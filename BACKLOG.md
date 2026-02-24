# GitPulse Backlog

## Current State

What's built and on main:
- github_client.py: Full async httpx client with 202 retry, rate limits, 7 endpoint methods. 20 tests.
- cache.py: File-based JSON cache with SHA256 keys, TTL, atomic writes. 14 tests.
- index.html: Complete frontend with all 8 chart types (ECharts + D3), KPI cards, loading skeletons, dark theme. ~1000 lines.

What's missing (the app does NOT work end-to-end yet):
- app.py only serves index.html -- no /api/analyze or /api/health endpoints wired
- git_analyzer.py is a stub docstring -- no implementation
- No tests for git_analyzer
- No integration between github_client, cache, git_analyzer, and app.py
- Frontend has no example repo chips or polish

## North Star

A user visits localhost:8000, pastes a GitHub repo URL, and sees a full dashboard
with all 8 visualizations populated from real data. The critical path is:

1. Wire /api/analyze in app.py (connect github_client + cache, return response schema)
2. Build git_analyzer.py (bare clone, hotspots, file tree, churn, survival curves)
3. Integrate git_analyzer into /api/analyze
4. End-to-end test with a real repo
5. Polish: error handling, example repo chips, mobile, README
