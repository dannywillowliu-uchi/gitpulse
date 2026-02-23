"""Tests for GitHubClient -- mock httpx responses."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from gitpulse.github_client import GitHubClient


@pytest.fixture
def mock_transport():
	"""Create a mock async transport for httpx."""
	return AsyncMock(spec=httpx.AsyncBaseTransport)


def _make_response(
	status_code: int = 200,
	json_data: dict | list | None = None,
	headers: dict[str, str] | None = None,
) -> httpx.Response:
	"""Build a fake httpx.Response."""
	resp = httpx.Response(
		status_code=status_code,
		json=json_data,
		headers=headers or {},
		request=httpx.Request("GET", "https://api.github.com/test"),
	)
	return resp


# --- Authentication ---


@pytest.mark.asyncio
async def test_auth_header_with_token():
	"""Token should produce Authorization header."""
	client = GitHubClient(token="ghp_test123")
	assert client._client.headers["Authorization"] == "Bearer ghp_test123"
	await client.close()


@pytest.mark.asyncio
async def test_no_auth_header_without_token():
	"""No token means no Authorization header."""
	with patch.dict("os.environ", {}, clear=True):
		client = GitHubClient()
		assert "Authorization" not in client._client.headers
		await client.close()


@pytest.mark.asyncio
async def test_token_from_env():
	"""Token picked up from GITHUB_TOKEN env var."""
	with patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_env_token"}):
		client = GitHubClient()
		assert client._client.headers["Authorization"] == "Bearer ghp_env_token"
		await client.close()


# --- fetch_with_retry: 200 success ---


@pytest.mark.asyncio
async def test_fetch_with_retry_200():
	"""Immediate 200 returns JSON data."""
	expected = [{"week": 1, "total": 5}]
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, expected))

	result = await client.fetch_with_retry("/repos/o/r/stats/commit_activity")
	assert result == expected


# --- fetch_with_retry: 202 then 200 ---


@pytest.mark.asyncio
async def test_fetch_with_retry_202_then_200():
	"""202 retries then succeeds on 200."""
	expected = {"data": "computed"}
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(
		side_effect=[
			_make_response(202, {}),
			_make_response(202, {}),
			_make_response(200, expected),
		]
	)

	with patch("gitpulse.github_client.asyncio.sleep", new_callable=AsyncMock):
		result = await client.fetch_with_retry("/repos/o/r/stats/contributors")

	assert result == expected
	assert client._client.get.call_count == 3


# --- fetch_with_retry: 202 exhausted ---


@pytest.mark.asyncio
async def test_fetch_with_retry_202_exhausted():
	"""5 consecutive 202s raises TimeoutError."""
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(202, {}))

	with patch("gitpulse.github_client.asyncio.sleep", new_callable=AsyncMock):
		with pytest.raises(TimeoutError, match="5 retries"):
			await client.fetch_with_retry("/repos/o/r/stats/punch_card")

	assert client._client.get.call_count == 5


# --- fetch_with_retry: 404 ---


@pytest.mark.asyncio
async def test_fetch_with_retry_404():
	"""404 raises HTTPStatusError immediately."""
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(404))

	with pytest.raises(httpx.HTTPStatusError):
		await client.fetch_with_retry("/repos/o/r/stats/commit_activity")

	assert client._client.get.call_count == 1


# --- fetch_with_retry: 500 ---


@pytest.mark.asyncio
async def test_fetch_with_retry_500():
	"""500 raises HTTPStatusError immediately."""
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	resp = _make_response(500)
	client._client.get = AsyncMock(return_value=resp)

	with pytest.raises(httpx.HTTPStatusError):
		await client.fetch_with_retry("/repos/o/r/stats/code_frequency")


# --- Rate limit warning ---


@pytest.mark.asyncio
async def test_rate_limit_warning(caplog):
	"""Warns when remaining < 10."""
	headers = {"X-RateLimit-Remaining": "5", "X-RateLimit-Reset": "9999999999"}
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, {}, headers))

	import logging

	with caplog.at_level(logging.WARNING, logger="gitpulse.github_client"):
		await client.fetch_with_retry("/repos/o/r/stats/punch_card")

	assert "rate limit low" in caplog.text.lower()


# --- Rate limit exhausted ---


@pytest.mark.asyncio
async def test_rate_limit_exhausted_sleeps():
	"""When remaining=0, sleeps until reset timestamp."""
	headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, {}, headers))

	with patch("gitpulse.github_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
		await client.fetch_with_retry("/repos/o/r/stats/punch_card")
		mock_sleep.assert_called_once()
		sleep_arg = mock_sleep.call_args[0][0]
		assert sleep_arg > 0


# --- get_repo ---


@pytest.mark.asyncio
async def test_get_repo_success():
	"""get_repo returns repo metadata."""
	repo_data = {"full_name": "owner/repo", "default_branch": "main"}
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, repo_data))

	result = await client.get_repo("owner", "repo")
	assert result == repo_data


@pytest.mark.asyncio
async def test_get_repo_404():
	"""get_repo raises on 404."""
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(404))

	with pytest.raises(httpx.HTTPStatusError):
		await client.get_repo("owner", "nonexistent")


# --- get_open_pulls ---


@pytest.mark.asyncio
async def test_get_open_pulls_success():
	"""get_open_pulls returns list of PRs."""
	prs = [{"number": 1, "title": "PR 1"}]
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, prs))

	result = await client.get_open_pulls("owner", "repo")
	assert result == prs


@pytest.mark.asyncio
async def test_get_open_pulls_404():
	"""get_open_pulls raises on 404."""
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(404))

	with pytest.raises(httpx.HTTPStatusError):
		await client.get_open_pulls("owner", "nonexistent")


# --- get_languages ---


@pytest.mark.asyncio
async def test_get_languages_success():
	"""get_languages returns language byte counts."""
	langs = {"Python": 35000, "JavaScript": 8000}
	client = GitHubClient(token="t")
	client._client = AsyncMock(spec=httpx.AsyncClient)
	client._client.get = AsyncMock(return_value=_make_response(200, langs))

	result = await client.get_languages("owner", "repo")
	assert result == langs


# --- Stats endpoints (via fetch_with_retry) ---


@pytest.mark.asyncio
async def test_get_commit_activity():
	"""get_commit_activity delegates to fetch_with_retry."""
	data = [{"week": 1704067200, "days": [0, 1, 2, 3, 4, 5, 6], "total": 21}]
	client = GitHubClient(token="t")
	client.fetch_with_retry = AsyncMock(return_value=data)

	result = await client.get_commit_activity("owner", "repo")
	assert result == data
	client.fetch_with_retry.assert_called_once_with(
		"/repos/owner/repo/stats/commit_activity"
	)


@pytest.mark.asyncio
async def test_get_code_frequency():
	"""get_code_frequency delegates to fetch_with_retry."""
	data = [[1704067200, 500, -120]]
	client = GitHubClient(token="t")
	client.fetch_with_retry = AsyncMock(return_value=data)

	result = await client.get_code_frequency("owner", "repo")
	assert result == data
	client.fetch_with_retry.assert_called_once_with(
		"/repos/owner/repo/stats/code_frequency"
	)


@pytest.mark.asyncio
async def test_get_contributors():
	"""get_contributors delegates to fetch_with_retry."""
	data = [{"author": {"login": "user1"}, "total": 50}]
	client = GitHubClient(token="t")
	client.fetch_with_retry = AsyncMock(return_value=data)

	result = await client.get_contributors("owner", "repo")
	assert result == data
	client.fetch_with_retry.assert_called_once_with(
		"/repos/owner/repo/stats/contributors"
	)


@pytest.mark.asyncio
async def test_get_punch_card():
	"""get_punch_card delegates to fetch_with_retry."""
	data = [[0, 14, 5]]
	client = GitHubClient(token="t")
	client.fetch_with_retry = AsyncMock(return_value=data)

	result = await client.get_punch_card("owner", "repo")
	assert result == data
	client.fetch_with_retry.assert_called_once_with(
		"/repos/owner/repo/stats/punch_card"
	)


# --- Context manager ---


@pytest.mark.asyncio
async def test_context_manager():
	"""GitHubClient works as async context manager."""
	async with GitHubClient(token="t") as client:
		assert isinstance(client, GitHubClient)
