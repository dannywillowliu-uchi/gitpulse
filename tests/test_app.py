from unittest.mock import AsyncMock, MagicMock, patch

import httpx


def test_index_returns_html(client):
	response = client.get("/")
	assert response.status_code == 200
	assert "GitPulse" in response.text
	assert "text/html" in response.headers["content-type"]


def test_health(client):
	response = client.get("/api/health")
	assert response.status_code == 200
	assert response.json() == {"status": "ok"}


def test_analyze_invalid_repo(client):
	response = client.get("/api/analyze?repo=invalid-no-slash")
	assert response.status_code == 400
	assert "Invalid repo format" in response.json()["detail"]


def test_analyze_missing_repo_param(client):
	response = client.get("/api/analyze")
	assert response.status_code == 422


@patch("gitpulse.app.GitHubClient")
def test_analyze_repo_not_found(mock_client_cls, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.side_effect = httpx.HTTPStatusError(
		"Not Found",
		request=MagicMock(),
		response=MagicMock(status_code=404),
	)
	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 404
	assert "not found" in response.json()["detail"].lower()


@patch("gitpulse.app.GitHubClient")
def test_analyze_github_error(mock_client_cls, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.side_effect = httpx.HTTPStatusError(
		"Internal Server Error",
		request=MagicMock(),
		response=MagicMock(status_code=500),
	)
	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 502
	assert "GitHub API error" in response.json()["detail"]


@patch("gitpulse.app.GitHubClient")
def test_analyze_timeout_error(mock_client_cls, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.side_effect = TimeoutError("GitHub still computing")
	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 502


@patch("gitpulse.app.cache")
@patch("gitpulse.app.GitHubClient")
def test_analyze_cache_hit(mock_client_cls, mock_cache, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.return_value = {"pushed_at": "2025-01-15T10:00:00Z"}
	mock_cache.get.return_value = {"repo": "owner/repo", "from_cache": True}

	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 200
	assert response.json()["from_cache"] is True
	mock_gh.get_commit_activity.assert_not_called()


@patch("gitpulse.app.analyze_repo", None)
@patch("gitpulse.app.cache")
@patch("gitpulse.app.GitHubClient")
def test_analyze_success(mock_client_cls, mock_cache, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.return_value = {
		"created_at": "2024-01-01T00:00:00Z",
		"default_branch": "main",
		"pushed_at": "2025-01-15T10:00:00Z",
	}
	mock_gh.get_commit_activity.return_value = [
		{"total": 10, "week": 1704067200, "days": [1, 2, 3, 0, 1, 2, 1]},
	]
	mock_gh.get_code_frequency.return_value = [
		[1704067200, 500, -120],
	]
	mock_gh.get_contributors.return_value = [
		{
			"author": {"login": "user1", "avatar_url": "https://example.com/a.png"},
			"total": 50,
			"weeks": [{"w": 1704067200, "a": 10, "d": 5, "c": 3}],
		},
	]
	mock_gh.get_punch_card.return_value = [[0, 14, 5]]
	mock_gh.get_open_pulls.return_value = [{"id": 1}, {"id": 2}]
	mock_gh.get_languages.return_value = {"Python": 35000, "JavaScript": 8000}
	mock_cache.get.return_value = None

	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 200
	data = response.json()

	assert data["repo"] == "owner/repo"
	assert "analyzed_at" in data
	assert data["summary"]["total_commits"] == 10
	assert data["summary"]["contributors"] == 1
	assert data["summary"]["loc"] == 43000
	assert data["summary"]["open_prs"] == 2
	assert data["summary"]["repo_age_days"] > 0
	assert data["summary"]["most_active_file"] == ""
	assert data["commit_activity"] == [
		{"week": 1704067200, "additions": 500, "deletions": 120}
	]
	assert data["punch_card"] == [{"day": 0, "hour": 14, "commits": 5}]
	assert data["contributors"][0]["login"] == "user1"
	assert data["contributors"][0]["total_commits"] == 50
	assert data["contributors"][0]["weekly_commits"] == [3]
	assert data["languages"] == {"Python": 35000, "JavaScript": 8000}
	assert data["hotspots"] == []
	assert data["file_tree"] == []
	assert data["survival_curves"] == []
	mock_cache.set.assert_called_once()


@patch("gitpulse.app.analyze_repo", new_callable=AsyncMock)
@patch("gitpulse.app.cache")
@patch("gitpulse.app.GitHubClient")
def test_analyze_success_with_git_data(mock_client_cls, mock_cache, mock_analyze, client):
	mock_gh = AsyncMock()
	mock_client_cls.return_value = mock_gh
	mock_gh.__aenter__.return_value = mock_gh
	mock_gh.get_repo.return_value = {
		"created_at": "2024-01-01T00:00:00Z",
		"default_branch": "main",
		"pushed_at": "2025-01-15T10:00:00Z",
	}
	mock_gh.get_commit_activity.return_value = [
		{"total": 10, "week": 1704067200, "days": [1, 2, 3, 0, 1, 2, 1]},
	]
	mock_gh.get_code_frequency.return_value = [[1704067200, 500, -120]]
	mock_gh.get_contributors.return_value = [
		{
			"author": {"login": "user1", "avatar_url": "https://example.com/a.png"},
			"total": 50,
			"weeks": [{"w": 1704067200, "a": 10, "d": 5, "c": 3}],
		},
	]
	mock_gh.get_punch_card.return_value = [[0, 14, 5]]
	mock_gh.get_open_pulls.return_value = [{"id": 1}]
	mock_gh.get_languages.return_value = {"Python": 35000}
	mock_cache.get.return_value = None
	mock_analyze.return_value = {
		"hotspots": [{"path": "src/main.py", "loc": 200, "change_count": 15, "directory": "src"}],
		"file_tree": [{"path": "src/main.py", "loc": 200, "churn": 42}],
		"survival_curves": [
			{"cohort": "2024-Q1", "data": [{"weeks_elapsed": 0, "surviving_lines": 1.0}]},
		],
	}

	response = client.get("/api/analyze?repo=owner/repo")
	assert response.status_code == 200
	data = response.json()

	mock_analyze.assert_awaited_once_with("https://github.com/owner/repo")
	assert data["hotspots"] == [
		{"path": "src/main.py", "loc": 200, "change_count": 15, "directory": "src"}
	]
	assert data["file_tree"] == [{"path": "src/main.py", "loc": 200, "churn": 42}]
	assert len(data["survival_curves"]) == 1
	assert data["summary"]["most_active_file"] == "src/main.py"
