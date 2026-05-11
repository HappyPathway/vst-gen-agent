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


def verify_github_repo_string(raw: str) -> str:
    """
    Parse, verify public, and return the normalized 'owner/repo' string.
    Raises ValueError on bad format, RepoNotPublicError if not public.
    """
    owner, repo = parse_github_repo(raw)
    verify_public_repo(owner, repo)
    return f"{owner}/{repo}"
