import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import Page, expect  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def test_homepage_loads(live_page: Page) -> None:
	"""Navigate to /, verify title, input field, and Analyze button are present."""
	expect(live_page.locator("h1")).to_contain_text("GitPulse")
	expect(live_page.locator("#repo-input")).to_be_visible()
	expect(live_page.locator("#analyze-btn")).to_be_visible()
	expect(live_page.locator("#analyze-btn")).to_have_text("Analyze")


def test_analyze_real_repo(live_page: Page) -> None:
	"""Analyze a small stable repo and verify KPIs and charts render."""
	live_page.fill("#repo-input", "keleshev/schema")
	live_page.click("#analyze-btn")

	# Wait for KPI section to appear (git clone can take a while)
	live_page.locator("#kpi-section").wait_for(state="visible", timeout=120_000)

	# Verify KPI values are non-zero integers
	commits_text = live_page.locator("#kpi-commits .text-3xl").inner_text()
	assert int(commits_text.replace(",", "")) > 0, f"Expected commits > 0, got {commits_text}"

	contributors_text = live_page.locator("#kpi-contributors .text-3xl").inner_text()
	assert int(contributors_text.replace(",", "")) > 0, (
		f"Expected contributors > 0, got {contributors_text}"
	)

	# Verify chart containers have rendered content (canvas for ECharts, SVG for D3)
	chart_ids = [
		"chart-timeline",
		"chart-heatmap",
		"chart-languages",
		"chart-survival",
	]
	for chart_id in chart_ids:
		canvas = live_page.locator(f"#{chart_id} canvas")
		expect(canvas.first).to_be_visible()

	# Contributor table should have rows
	expect(live_page.locator("#contributor-tbody tr").first).to_be_visible()

	# D3 charts render SVG elements
	d3_chart_ids = ["chart-hotspots", "chart-treemap"]
	for chart_id in d3_chart_ids:
		svg = live_page.locator(f"#{chart_id} svg")
		expect(svg.first).to_be_visible()


def test_invalid_repo_shows_error(live_page: Page) -> None:
	"""Submit a nonexistent repo and verify error banner appears."""
	live_page.fill("#repo-input", "nonexistent/repo-that-does-not-exist-xyz")
	live_page.click("#analyze-btn")

	error_banner = live_page.locator("#error-banner")
	error_banner.wait_for(state="visible", timeout=30_000)

	error_text = live_page.locator("#error-message").inner_text()
	assert len(error_text) > 0, "Error message should not be empty"


def test_loading_skeleton_appears(live_page: Page) -> None:
	"""Submit a repo and immediately verify skeleton loaders are shown."""
	live_page.fill("#repo-input", "keleshev/schema")
	live_page.click("#analyze-btn")

	# Skeleton should appear immediately while loading
	kpi_skeleton = live_page.locator("#kpi-skeleton")
	kpi_skeleton.wait_for(state="visible", timeout=5_000)

	charts_skeleton = live_page.locator("#charts-skeleton")
	expect(charts_skeleton).to_be_visible()
