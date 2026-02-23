"""Local git repository analyzer.

Performs bare clone into temp directory and extracts:
- File hotspots (change frequency per file)
- File tree with lines of code
- Code churn per file (additions/deletions over time)
- Code survival curves (quarter-cohort line survival rates)

Uses subprocess for git commands (not gitpython).
"""
