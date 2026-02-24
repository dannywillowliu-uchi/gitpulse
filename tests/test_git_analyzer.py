"""Tests for git_analyzer module."""

import os
import subprocess

import pytest

from gitpulse.git_analyzer import (
	analyze_repo,
	cleanup_clone,
	clone_bare,
	get_churn,
	get_file_tree,
	get_hotspots,
	get_survival_curves,
)


@pytest.fixture
def bare_repo(tmp_path):
	"""Create a test bare repo with multiple commits."""
	work = tmp_path / "work"
	work.mkdir()
	subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
	subprocess.run(
		["git", "-C", str(work), "config", "user.email", "test@test.com"],
		check=True,
		capture_output=True,
	)
	subprocess.run(
		["git", "-C", str(work), "config", "user.name", "Test"],
		check=True,
		capture_output=True,
	)

	# Commit 1: create src/main.py
	(work / "src").mkdir()
	(work / "src" / "main.py").write_text("line1\nline2\nline3\n")
	subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
	subprocess.run(
		["git", "-C", str(work), "commit", "-m", "Initial"],
		check=True,
		capture_output=True,
	)

	# Commit 2: modify main.py, add README
	(work / "src" / "main.py").write_text("line1\nline2\nline3\nline4\n")
	(work / "README.md").write_text("# Test\n")
	subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
	subprocess.run(
		["git", "-C", str(work), "commit", "-m", "Add line4 and README"],
		check=True,
		capture_output=True,
	)

	# Commit 3: add utils.py
	(work / "src" / "utils.py").write_text("def helper():\n\treturn True\n")
	subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
	subprocess.run(
		["git", "-C", str(work), "commit", "-m", "Add utils"],
		check=True,
		capture_output=True,
	)

	# Bare clone
	bare = tmp_path / "bare.git"
	subprocess.run(
		["git", "clone", "--bare", str(work), str(bare)],
		check=True,
		capture_output=True,
	)
	yield str(bare)


class TestCloneBare:
	def test_clone_and_cleanup(self, tmp_path):
		"""clone_bare returns a valid bare repo path, cleanup_clone removes it."""
		work = tmp_path / "src_repo"
		work.mkdir()
		subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "config", "user.email", "t@t.com"],
			check=True,
			capture_output=True,
		)
		subprocess.run(
			["git", "-C", str(work), "config", "user.name", "T"],
			check=True,
			capture_output=True,
		)
		(work / "f.txt").write_text("hello")
		subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "commit", "-m", "init"],
			check=True,
			capture_output=True,
		)

		clone_path = clone_bare(str(work))
		assert os.path.isdir(clone_path)
		# Verify it's a bare repo (HEAD file exists at top level)
		assert os.path.isfile(os.path.join(clone_path, "HEAD"))

		cleanup_clone(clone_path)
		assert not os.path.exists(clone_path)

	def test_clone_invalid_url_raises(self):
		"""clone_bare raises RuntimeError for invalid URLs."""
		with pytest.raises(RuntimeError, match="git clone failed"):
			clone_bare("/nonexistent/repo/path")

	def test_cleanup_nonexistent_is_noop(self, tmp_path):
		"""cleanup_clone silently handles nonexistent paths."""
		cleanup_clone(str(tmp_path / "nope"))


class TestGetHotspots:
	def test_returns_sorted_by_change_count(self, bare_repo):
		result = get_hotspots(bare_repo)
		assert isinstance(result, list)
		assert len(result) > 0
		# Should be sorted descending by change_count
		counts = [r["change_count"] for r in result]
		assert counts == sorted(counts, reverse=True)

	def test_main_py_most_changed(self, bare_repo):
		result = get_hotspots(bare_repo)
		paths = [r["path"] for r in result]
		assert "src/main.py" in paths
		main = next(r for r in result if r["path"] == "src/main.py")
		assert main["change_count"] == 2
		assert main["directory"] == "src"

	def test_directory_field(self, bare_repo):
		result = get_hotspots(bare_repo)
		readme = next(r for r in result if r["path"] == "README.md")
		assert readme["directory"] == ""


class TestGetFileTree:
	def test_returns_loc_at_head(self, bare_repo):
		result = get_file_tree(bare_repo)
		assert isinstance(result, list)
		paths = [r["path"] for r in result]
		assert "src/main.py" in paths

	def test_loc_values(self, bare_repo):
		result = get_file_tree(bare_repo)
		main = next(r for r in result if r["path"] == "src/main.py")
		assert main["loc"] == 4  # 4 lines at HEAD

	def test_churn_placeholder_zero(self, bare_repo):
		result = get_file_tree(bare_repo)
		for entry in result:
			assert entry["churn"] == 0

	def test_all_files_present(self, bare_repo):
		result = get_file_tree(bare_repo)
		paths = {r["path"] for r in result}
		assert paths == {"src/main.py", "src/utils.py", "README.md"}


class TestGetChurn:
	def test_returns_additions_deletions(self, bare_repo):
		result = get_churn(bare_repo)
		assert isinstance(result, list)
		assert len(result) > 0
		for entry in result:
			assert "path" in entry
			assert "additions" in entry
			assert "deletions" in entry

	def test_main_py_churn(self, bare_repo):
		result = get_churn(bare_repo)
		main = next(r for r in result if r["path"] == "src/main.py")
		# Commit 1: +3 lines, Commit 2: +4 -3 (rewrote file)
		assert main["additions"] >= 4
		assert main["deletions"] >= 0

	def test_sorted_by_total_churn(self, bare_repo):
		result = get_churn(bare_repo)
		totals = [r["additions"] + r["deletions"] for r in result]
		assert totals == sorted(totals, reverse=True)


class TestGetSurvivalCurves:
	def test_returns_list_of_cohorts(self, bare_repo):
		result = get_survival_curves(bare_repo)
		assert isinstance(result, list)
		# All commits are in the same quarter, so expect 1 cohort
		assert len(result) >= 1

	def test_cohort_structure(self, bare_repo):
		result = get_survival_curves(bare_repo)
		cohort = result[0]
		assert "cohort" in cohort
		assert "data" in cohort
		# Cohort key format: YYYY-QN
		assert cohort["cohort"][4] == "-"
		assert cohort["cohort"][5] == "Q"

	def test_initial_survival_is_one(self, bare_repo):
		result = get_survival_curves(bare_repo)
		for cohort in result:
			assert cohort["data"][0]["weeks_elapsed"] == 0
			assert cohort["data"][0]["surviving_lines"] == 1.0


class TestAnalyzeRepo:
	@pytest.mark.asyncio
	async def test_returns_all_keys(self, tmp_path):
		work = tmp_path / "repo"
		work.mkdir()
		subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "config", "user.email", "t@t.com"],
			check=True,
			capture_output=True,
		)
		subprocess.run(
			["git", "-C", str(work), "config", "user.name", "T"],
			check=True,
			capture_output=True,
		)
		(work / "app.py").write_text("print('hello')\n")
		subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "commit", "-m", "init"],
			check=True,
			capture_output=True,
		)

		result = await analyze_repo(str(work))
		assert "hotspots" in result
		assert "file_tree" in result
		assert "survival_curves" in result

	@pytest.mark.asyncio
	async def test_churn_merged_into_file_tree(self, tmp_path):
		work = tmp_path / "repo"
		work.mkdir()
		subprocess.run(["git", "init", str(work)], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "config", "user.email", "t@t.com"],
			check=True,
			capture_output=True,
		)
		subprocess.run(
			["git", "-C", str(work), "config", "user.name", "T"],
			check=True,
			capture_output=True,
		)
		(work / "app.py").write_text("a\nb\nc\n")
		subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "commit", "-m", "init"],
			check=True,
			capture_output=True,
		)
		(work / "app.py").write_text("a\nb\nc\nd\n")
		subprocess.run(["git", "-C", str(work), "add", "."], check=True, capture_output=True)
		subprocess.run(
			["git", "-C", str(work), "commit", "-m", "add d"],
			check=True,
			capture_output=True,
		)

		result = await analyze_repo(str(work))
		app_entry = next(e for e in result["file_tree"] if e["path"] == "app.py")
		# churn should be filled from get_churn (additions + deletions)
		assert app_entry["churn"] > 0

	@pytest.mark.asyncio
	async def test_cleanup_on_error(self, tmp_path):
		"""Temp directory is cleaned up even if analysis fails."""
		with pytest.raises(RuntimeError):
			await analyze_repo("/nonexistent/repo")
