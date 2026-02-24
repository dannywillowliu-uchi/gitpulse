"""Local git repository analyzer.

Performs bare clone into temp directory and extracts:
- File hotspots (change frequency per file)
- File tree with lines of code
- Code churn per file (additions/deletions over time)
- Code survival curves (quarter-cohort line survival rates)

Uses subprocess for git commands (not gitpython).
"""

import asyncio
import logging
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def clone_bare(repo_url: str) -> str:
	"""Clone repo as bare into temp directory, return path."""
	tmp_dir = tempfile.mkdtemp(prefix="gitpulse-")
	try:
		result = subprocess.run(
			["git", "clone", "--bare", repo_url, tmp_dir],
			capture_output=True,
			text=True,
			timeout=60,
		)
		if result.returncode != 0:
			raise RuntimeError(f"git clone failed: {result.stderr.strip()}")
		logger.info("Cloned %s to %s", repo_url, tmp_dir)
		return tmp_dir
	except Exception:
		shutil.rmtree(tmp_dir, ignore_errors=True)
		raise


def cleanup_clone(clone_path: str) -> None:
	"""Remove the temp clone directory."""
	shutil.rmtree(clone_path, ignore_errors=True)
	logger.info("Cleaned up %s", clone_path)


def _run_git(bare_path: str, *args: str) -> subprocess.CompletedProcess[str]:
	"""Run a git command against a bare repo, raising on failure."""
	result = subprocess.run(
		["git", "-C", bare_path, *args],
		capture_output=True,
		text=True,
		timeout=60,
	)
	if result.returncode != 0:
		raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
	return result


def get_hotspots(bare_path: str) -> list[dict]:
	"""Count commits per file, return sorted by frequency descending."""
	result = _run_git(bare_path, "log", "--format=", "--name-only")

	counts: dict[str, int] = {}
	for line in result.stdout.splitlines():
		path = line.strip()
		if path:
			counts[path] = counts.get(path, 0) + 1

	return [
		{
			"path": path,
			"change_count": count,
			"directory": path.split("/")[0] if "/" in path else "",
		}
		for path, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)
	]


def get_file_tree(bare_path: str) -> list[dict]:
	"""Get LOC per file at HEAD using diff against empty tree."""
	empty_tree = _run_git(bare_path, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
	result = _run_git(bare_path, "diff", "--numstat", empty_tree, "HEAD")

	file_tree = []
	for line in result.stdout.splitlines():
		line = line.strip()
		if not line:
			continue
		parts = line.split("\t")
		if len(parts) >= 3:
			add_str = parts[0]
			path = parts[2]
			loc = int(add_str) if add_str != "-" else 0
			file_tree.append({"path": path, "loc": loc, "churn": 0})

	return file_tree


def get_churn(bare_path: str) -> list[dict]:
	"""Sum additions and deletions per file over full history."""
	result = _run_git(bare_path, "log", "--numstat", "--format=")

	churn: dict[str, dict[str, int]] = {}
	for line in result.stdout.splitlines():
		line = line.strip()
		if not line:
			continue
		parts = line.split("\t")
		if len(parts) >= 3:
			add_str, del_str, path = parts[0], parts[1], parts[2]
			additions = int(add_str) if add_str != "-" else 0
			deletions = int(del_str) if del_str != "-" else 0
			if path not in churn:
				churn[path] = {"additions": 0, "deletions": 0}
			churn[path]["additions"] += additions
			churn[path]["deletions"] += deletions

	return [
		{"path": p, "additions": d["additions"], "deletions": d["deletions"]}
		for p, d in sorted(
			churn.items(),
			key=lambda x: x[1]["additions"] + x[1]["deletions"],
			reverse=True,
		)
	]


def _quarter_dates(cohort_key: str) -> tuple[str, str, datetime]:
	"""Return (after_date, before_date, cohort_end_dt) for a quarter.

	after_date/before_date are exclusive bounds for git --after/--before.
	"""
	year_str, q_str = cohort_key.split("-Q")
	year, q = int(year_str), int(q_str)
	# --after is exclusive (strictly after), --before is exclusive (strictly before)
	starts = {1: (year - 1, 12, 31), 2: (year, 3, 31), 3: (year, 6, 30), 4: (year, 9, 30)}
	ends = {1: (year, 4, 1), 2: (year, 7, 1), 3: (year, 10, 1), 4: (year + 1, 1, 1)}
	end_dts = {1: (year, 3, 31), 2: (year, 6, 30), 3: (year, 9, 30), 4: (year, 12, 31)}
	sy, sm, sd = starts[q]
	ey, em, ed = ends[q]
	edy, edm, edd = end_dts[q]
	return (
		f"{sy}-{sm:02d}-{sd:02d}",
		f"{ey}-{em:02d}-{ed:02d}",
		datetime(edy, edm, edd, tzinfo=timezone.utc),
	)


def _count_surviving_lines(
	bare_path: str, rev: str, files: set[str], cohort_shas: set[str]
) -> int:
	"""Count lines at rev that were authored by commits in cohort_shas."""
	surviving = 0
	for filepath in files:
		try:
			blame_result = subprocess.run(
				["git", "-C", bare_path, "blame", "--porcelain", rev, "--", filepath],
				capture_output=True,
				text=True,
				timeout=60,
			)
		except subprocess.TimeoutExpired:
			logger.warning("Blame timed out for %s at %s", filepath, rev)
			continue
		if blame_result.returncode != 0:
			continue  # file may have been deleted at this revision
		for blame_line in blame_result.stdout.splitlines():
			if blame_line.startswith("\t"):
				continue
			parts = blame_line.split()
			if len(parts) >= 3:
				sha = parts[0]
				if len(sha) == 40 and sha in cohort_shas:
					surviving += 1
	return surviving


def get_survival_curves(bare_path: str) -> list[dict]:
	"""Compute code survival curves by quarterly cohort.

	Groups commits by quarter, counts lines added per cohort, then samples
	git blame at 4-week intervals to measure how many lines survive.
	"""
	result = _run_git(bare_path, "log", "--format=%H %aI")

	commits: list[tuple[str, datetime]] = []
	for line in result.stdout.splitlines():
		line = line.strip()
		if not line:
			continue
		sha, date_str = line.split(" ", 1)
		commits.append((sha, datetime.fromisoformat(date_str)))

	if not commits:
		return []

	# Group by quarter
	cohort_commits: dict[str, set[str]] = defaultdict(set)
	for sha, dt in commits:
		quarter = (dt.month - 1) // 3 + 1
		cohort_commits[f"{dt.year}-Q{quarter}"].add(sha)

	sorted_keys = sorted(cohort_commits.keys())[-8:]
	if not sorted_keys:
		return []

	head_date = max(dt for _, dt in commits)
	if head_date.tzinfo is None:
		head_date = head_date.replace(tzinfo=timezone.utc)

	curves: list[dict] = []
	for cohort_key in sorted_keys:
		shas = cohort_commits[cohort_key]
		after_date, before_date, cohort_end_dt = _quarter_dates(cohort_key)

		# Get total lines added and files changed for this cohort
		try:
			numstat_result = _run_git(
				bare_path,
				"log",
				"--numstat",
				"--format=",
				f"--after={after_date}",
				f"--before={before_date}",
			)
		except RuntimeError:
			continue

		total_added = 0
		files_changed: set[str] = set()
		for stat_line in numstat_result.stdout.splitlines():
			stat_line = stat_line.strip()
			if not stat_line:
				continue
			parts = stat_line.split("\t")
			if len(parts) >= 3 and parts[0] != "-":
				total_added += int(parts[0])
				files_changed.add(parts[2])

		if total_added == 0:
			curves.append({
				"cohort": cohort_key,
				"data": [{"weeks_elapsed": 0, "surviving_lines": 1.0}],
			})
			continue

		# Sample survival at 4-week intervals
		data: list[dict] = [{"weeks_elapsed": 0, "surviving_lines": 1.0}]

		for weeks in range(4, 53, 4):
			sample_dt = cohort_end_dt + timedelta(weeks=weeks)
			if sample_dt > head_date.astimezone(timezone.utc):
				break

			# Find nearest commit before sample date
			try:
				rev_result = _run_git(
					bare_path,
					"rev-list",
					"-1",
					f"--before={sample_dt.isoformat()}",
					"HEAD",
				)
			except RuntimeError:
				continue
			sample_rev = rev_result.stdout.strip()
			if not sample_rev:
				continue

			surviving = _count_surviving_lines(bare_path, sample_rev, files_changed, shas)
			survival_rate = min(surviving / total_added, 1.0)
			data.append({
				"weeks_elapsed": weeks,
				"surviving_lines": round(survival_rate, 4),
			})

		curves.append({"cohort": cohort_key, "data": data})

	return curves


async def analyze_repo(repo_url: str) -> dict:
	"""Clone repo, run all analyses, return combined results.

	Clones the repo as bare, runs hotspot/file_tree/churn/survival analyses
	concurrently, merges churn into file_tree, then cleans up.
	"""
	clone_path = await asyncio.to_thread(clone_bare, repo_url)
	try:
		hotspots, file_tree, churn, survival = await asyncio.gather(
			asyncio.to_thread(get_hotspots, clone_path),
			asyncio.to_thread(get_file_tree, clone_path),
			asyncio.to_thread(get_churn, clone_path),
			asyncio.to_thread(get_survival_curves, clone_path),
		)

		# Merge churn into file_tree
		churn_map = {item["path"]: item["additions"] + item["deletions"] for item in churn}
		for entry in file_tree:
			entry["churn"] = churn_map.get(entry["path"], 0)

		return {
			"hotspots": hotspots,
			"file_tree": file_tree,
			"survival_curves": survival,
		}
	finally:
		await asyncio.to_thread(cleanup_clone, clone_path)
