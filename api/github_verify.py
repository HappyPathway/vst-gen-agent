"""
github_verify.py — verify that a GitHub repo exists and is public.

Uses the unauthenticated GitHub REST API v3:
  GET https://api.github.com/repos/{owner}/{repo}

Public repos return 200 with `"private": false`.
Private repos return 404 (GitHub hides them from unauthenticated callers).
We block indexing for anything that is not provably public.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


# matches "owner/repo" or a full https://github.com/owner/repo URL
_REPO_RE = re.compile(
    r"^(?:https?://github\.com/)?([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+?)(?:\.git)?$"
)

GITHUB_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "vst-gen-registry/1.0",
}


def parse_github_repo(raw: str) -> tuple[str, str]:
    """
    Parse a repo reference into (owner, repo).
    Accepts:
      - "HappyPathway/Take5-VST"
      - "https://github.com/HappyPathway/Take5-VST"
      - "https://github.com/HappyPathway/Take5-VST.git"

    Raises ValueError if the format is unrecognized.
    """
    m = _REPO_RE.match(raw.strip())
    if not m:
        raise ValueError(
            f"Cannot parse GitHub repo reference: {raw!r}. "
            "Expected 'owner/repo' or 'https://github.com/owner/repo'."
        )
    return m.group(1), m.group(2)


def normalize_github_repo(raw: str) -> str:
    """Return canonical 'owner/repo' form, or raise ValueError."""
    owner, repo = parse_github_repo(raw)
    return f"{owner}/{repo}"


class RepoNotPublicError(Exception):
    """Raised when the repo is private or does not exist."""


def verify_public_repo(owner: str, repo: str) -> dict:
    """
    Call the GitHub API and verify the repo is public.

    Returns the GitHub API response dict on success.
    Raises RepoNotPublicError if the repo is private, missing, or the API
    call fails in a way that prevents verification.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(url, headers=GITHUB_API_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RepoNotPublicError(
                f"GitHub repo '{owner}/{repo}' not found or is private. "
                "Only public repositories can be indexed in the registry."
            ) from exc
        raise RepoNotPublicError(
            f"GitHub API returned HTTP {exc.code} for '{owner}/{repo}'. "
            "Cannot verify visibility — indexing blocked."
        ) from exc
    except OSError as exc:
        raise RepoNotPublicError(
            f"Network error reaching GitHub API: {exc}. "
            "Cannot verify repo visibility — indexing blocked."
        ) from exc

    if data.get("private"):
        raise RepoNotPublicError(
            f"GitHub repo '{owner}/{repo}' is private. "
            "Set the repository to public before submitting to the registry."
        )

    return data


class RepoPanelMissingError(Exception):
    """Raised when panel.png is not found at the expected raw GitHub URL."""


class RepoEmptyError(Exception):
    """Raised when the repo exists and is public but has no commits yet."""


def verify_repo_has_commits(owner: str, repo: str) -> None:
    """
    Check that the repo has at least one commit via the commits API.
    An empty repo is public but has no pushable content — block indexing.
    Raises RepoEmptyError if empty, RepoNotPublicError on API failure.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1"
    req = urllib.request.Request(url, headers=GITHUB_API_HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            commits = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (409, 404):
            # 409 = Git Repository is empty, 404 = missing
            raise RepoEmptyError(
                f"GitHub repo '{owner}/{repo}' exists but has no commits. "
                "Push your code before submitting to the registry."
            ) from exc
        raise RepoNotPublicError(
            f"GitHub API returned HTTP {exc.code} checking commits for '{owner}/{repo}'."
        ) from exc
    except OSError as exc:
        raise RepoNotPublicError(
            f"Network error checking commits for '{owner}/{repo}': {exc}"
        ) from exc

    if not commits:
        raise RepoEmptyError(
            f"GitHub repo '{owner}/{repo}' has no commits. "
            "Push your code before submitting to the registry."
        )


def verify_panel_exists(owner: str, repo: str) -> None:
    """
    Verify that panel.png exists at the raw GitHub URL.
    Uses HEAD request to avoid downloading the file.
    Raises RepoPanelMissingError if not found.
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/panel.png"
    req = urllib.request.Request(url, headers=GITHUB_API_HEADERS, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=8):
            pass  # 200 OK — file exists
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RepoPanelMissingError(
                f"panel.png not found in '{owner}/{repo}' at HEAD. "
                "Commit and push panel.png to the repo root before submitting."
            ) from exc
        # Non-404 HTTP errors: treat as soft warning (CDN may be slow), don't block
    except OSError:
        pass  # network glitch — don't block submission on transient CDN issues


def verify_github_repo_string(raw: str) -> str:
    """
    Parse, verify public + non-empty, and return the normalized 'owner/repo' string.
    Raises ValueError on bad format.
    Raises RepoNotPublicError if private or unreachable.
    Raises RepoEmptyError if the repo has no commits.
    panel.png check is advisory (RepoPanelMissingError) — callers decide whether to block.
    """
    owner, repo = parse_github_repo(raw)
    verify_public_repo(owner, repo)
    verify_repo_has_commits(owner, repo)
    return f"{owner}/{repo}"


def full_verify(raw: str) -> tuple[str, list[str]]:
    """
    Full verification: public + has commits + panel.png exists.
    Returns (normalized_slug, warnings).
    warnings is non-empty if panel.png is missing (soft warning, not a hard block).
    Raises ValueError / RepoNotPublicError / RepoEmptyError on hard failures.
    """
    owner, repo = parse_github_repo(raw)
    verify_public_repo(owner, repo)
    verify_repo_has_commits(owner, repo)
    warnings = []
    try:
        verify_panel_exists(owner, repo)
    except RepoPanelMissingError as exc:
        warnings.append(str(exc))
    return f"{owner}/{repo}", warnings


def revalidate_repo(raw: str) -> tuple[bool, str]:
    """
    Re-check an already-indexed repo for continued public + non-empty status.
    Returns (is_valid, reason).
    Used by the background revalidation job.
    """
    try:
        owner, repo = parse_github_repo(raw)
        verify_public_repo(owner, repo)
        verify_repo_has_commits(owner, repo)
        return True, "ok"
    except (RepoNotPublicError, RepoEmptyError, ValueError) as exc:
        return False, str(exc)
