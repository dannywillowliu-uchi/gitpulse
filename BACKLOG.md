# GitPulse Backlog

## Current State

Core backend is fully implemented and integrated. The app works end-to-end.

What's built and on main:
- github_client.py: Full async httpx client with 202 retry, rate limits, 7 endpoint methods. 20 tests.
- cache.py: File-based JSON cache with SHA256 keys, TTL, atomic writes. 14 tests.
- git_analyzer.py: Full implementation -- bare clone, hotspots (with LOC), file tree, churn, survival curves, analyze_repo wrapper. Tests in test_git_analyzer.py.
- app.py: FastAPI app with GET /, GET /api/health, GET /api/analyze routes. Uses analyze_repo wrapper for git analysis. Tests in test_app.py.
- index.html: Complete frontend with all 8 chart types (ECharts + D3), KPI cards, loading skeletons, dark theme. ~1000 lines.

What's remaining (polish / nice-to-have):
- Frontend example repo chips
- Mobile responsiveness polish
- README documentation
- End-to-end test with a real repo (Playwright E2E tests exist but need real integration testing)

## North Star

A user visits localhost:8000, pastes a GitHub repo URL, and sees a full dashboard
with all 8 visualizations populated from real data. The critical path is:

1. ~~Wire /api/analyze in app.py (connect github_client + cache, return response schema)~~ DONE
2. ~~Build git_analyzer.py (bare clone, hotspots, file tree, churn, survival curves)~~ DONE
3. ~~Integrate git_analyzer into /api/analyze~~ DONE
4. End-to-end test with a real repo
5. Polish: error handling, example repo chips, mobile, README
