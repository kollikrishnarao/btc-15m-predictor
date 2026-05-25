"""
Twitter Research — Shared Utilities
GitHub API client, link extraction, Nitter fallback, sentiment scoring.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import random
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx

log = logging.getLogger("twitter_research")


# ─────────────────────────────────────────────────────────────────────────────
# GitHub API Client (no auth — 60 req/hr limit)
# ─────────────────────────────────────────────────────────────────────────────

class GitHubClient:
    """Fetch GitHub repo metadata without authentication."""

    BASE_URL = "https://api.github.com"
    _cache: dict[str, dict] = {}

    async def fetch_repo(
        self,
        owner: str,
        repo: str,
        include_readme: bool = False,
    ) -> dict | None:
        """
        Fetch repo metadata from GitHub public API.
        Caches results for 1 hour to stay within rate limits.
        """
        key = f"{owner}/{repo}"
        if key in self._cache:
            return self._cache[key]

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch repo metadata
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{owner}/{repo}",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                if resp.status_code == 404:
                    return None
                if resp.status_code == 403:
                    log.warning(f"GitHub rate limit hit for {key}")
                    return {"error": "rate_limit", "repo": key}

                data = resp.json()
                result = {
                    "name": data.get("name"),
                    "full_name": data.get("full_name"),
                    "description": data.get("description") or "",
                    "stars": data.get("stargazers_count", 0),
                    "forks": data.get("forks_count", 0),
                    "language": data.get("language") or "",
                    "topics": data.get("topics", []),
                    "url": data.get("html_url"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "homepage": data.get("homepage") or "",
                    "license": (data.get("license") or {}).get("name", ""),
                    "open_issues": data.get("open_issues_count", 0),
                }

                # Optionally fetch README
                if include_readme:
                    readme_resp = await client.get(
                        f"{self.BASE_URL}/repos/{owner}/{repo}/readme",
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )
                    if readme_resp.status_code == 200:
                        content_b64 = readme_resp.json().get("content", "")
                        try:
                            result["readme"] = base64.b64decode(content_b64).decode("utf-8")[:2000]
                        except Exception:
                            result["readme"] = ""

                self._cache[key] = result
                return result

        except Exception as e:
            log.debug(f"GitHub fetch failed for {owner}/{repo}: {e}")
            return {"error": str(e), "repo": key}

    def clear_cache(self):
        self._cache.clear()


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Link Extraction
# ─────────────────────────────────────────────────────────────────────────────

_GITHUB_PATTERNS = [
    re.compile(r'https?://(?:www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'),
    re.compile(r'github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)'),
]


def extract_github_repos(text: str, urls: list[str] | None = None) -> list[dict]:
    """
    Extract all GitHub repo references from tweet text and URLs.
    Returns list of dicts: [{owner, repo, url}, ...]
    """
    repos = []
    seen = set()

    sources = [text] + (urls or [])
    for source in sources:
        if not source:
            continue
        for pattern in _GITHUB_PATTERNS:
            for match in pattern.finditer(source):
                owner, repo = match.group(1), match.group(2)
                # Strip trailing /issues, /pull, /blob, etc.
                repo = repo.split("/")[0]
                key = f"{owner}/{repo}"
                if key not in seen and owner not in ("github", "vs", "settings"):
                    seen.add(key)
                    repos.append({
                        "owner": owner,
                        "repo": repo,
                        "full_name": key,
                        "url": f"https://github.com/{owner}/{repo}",
                    })
    return repos


# ─────────────────────────────────────────────────────────────────────────────
# General URL Extraction
# ─────────────────────────────────────────────────────────────────────────────

_URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


def extract_urls(text: str) -> list[str]:
    """Extract all HTTP(S) URLs from text."""
    return list(set(_URL_PATTERN.findall(text)))


# ─────────────────────────────────────────────────────────────────────────────
# Sentiment Analysis
# ─────────────────────────────────────────────────────────────────────────────

_BULLISH_KW = {
    "bullish", "long", "buy", "accumulate", "breakout", "moon", "pump",
    "up", "green", "support", "dip", "call", "long", "hodl", "btfd",
    "win", "winning", "gains", "profit", "launch", "released", "new",
}
_BEARISH_KW = {
    "bearish", "short", "sell", "drop", "breakdown", "crash", "dump",
    "down", "red", "resistance", "liquidat", "sell", "rekt", "loss",
    "hack", "scam", "fail", "broken", "bug", "exploit",
}
_NEUTRAL_KW = {
    "neutral", "watch", "wait", "range", "sideways", "uncertain",
    "discuss", "thoughts", "maybe", "perhaps", "not sure",
}


def compute_sentiment(text: str) -> dict[str, int]:
    """Compute keyword-based sentiment counts from tweet text."""
    text_lower = text.lower()
    return {
        "bullish": sum(1 for kw in _BULLISH_KW if kw in text_lower),
        "bearish": sum(1 for kw in _BEARISH_KW if kw in text_lower),
        "neutral": sum(1 for kw in _NEUTRAL_KW if kw in text_lower),
    }


def sentiment_label(bullish: int, bearish: int, neutral: int) -> str:
    """Label sentiment from keyword counts."""
    if bullish > bearish * 1.5:
        return "BULLISH"
    elif bearish > bullish * 1.5:
        return "BEARISH"
    return "NEUTRAL"


# ─────────────────────────────────────────────────────────────────────────────
# Nitter Fallback (free, no credentials)
# ─────────────────────────────────────────────────────────────────────────────

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.fly.dev",
]


async def search_via_nitter(
    query: str,
    limit: int = 15,
    timeout: float = 10.0,
) -> list[dict]:
    """
    Fallback search via Nitter RSS (no credentials needed).
    Attempts multiple instances in sequence.
    """
    for base_url in NITTER_INSTANCES:
        try:
            encoded = query.replace(" ", "%20")
            url = f"{base_url}/search?f=tweets&q={encoded}"

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                tweets = _parse_nitter_search(resp.text, limit)
                if tweets:
                    log.debug(f"Nitter fallback succeeded via {base_url}")
                    return tweets

        except Exception as e:
            log.debug(f"Nitter {base_url} failed: {e}")
            continue

    return []


async def fetch_user_via_nitter(
    username: str,
    limit: int = 10,
    timeout: float = 10.0,
) -> list[dict]:
    """Fetch a user's recent tweets via Nitter."""
    for base_url in NITTER_INSTANCES:
        try:
            url = f"{base_url}/{username}"

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url, follow_redirects=True)
                if resp.status_code != 200:
                    continue

                return _parse_nitter_user(resp.text, limit)

        except Exception as e:
            log.debug(f"Nitter user fetch {base_url} failed: {e}")
            continue

    return []


def _parse_nitter_search(html: str, limit: int) -> list[dict]:
    """Parse tweets from Nitter search HTML."""
    tweets = []
    pattern = re.compile(
        r'<div class="tweet-content[^"]*">(.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(html)
    for i, match in enumerate(matches[:limit]):
        clean = re.sub(r"<[^>]+>", " ", match).strip()
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if len(clean) > 10:
            tweets.append({
                "id": f"nitter_{i}",
                "text": clean[:500],
                "username": "unknown",
                "source": "nitter",
            })
    return tweets


def _parse_nitter_user(html: str, limit: int) -> list[dict]:
    """Parse user timeline from Nitter HTML."""
    return _parse_nitter_search(html, limit)


# ─────────────────────────────────────────────────────────────────────────────
# Rate Limiter
# ─────────────────────────────────────────────────────────────────────────────

class RateLimiter:
    """Human-like delay + exponential backoff."""

    def __init__(
        self,
        base_delay: float = 3.0,
        jitter: float = 2.0,
        max_delay: float = 120.0,
    ):
        self.base_delay = base_delay
        self.jitter = jitter
        self.max_delay = max_delay
        self._failures: dict[str, int] = {}

    async def wait(self, label: str = "default"):
        """Apply human-like random delay."""
        base = self.base_delay + random.uniform(0, self.jitter)
        failures = self._failures.get(label, 0)
        if failures > 0:
            delay = min(base * (2 ** min(failures, 5)), self.max_delay)
        else:
            delay = base
        await asyncio.sleep(delay)

    def on_success(self, label: str = "default"):
        self._failures[label] = 0

    def on_failure(self, label: str = "default"):
        self._failures[label] = self._failures.get(label, 0) + 1

    def is_rate_limit(self, error: str) -> bool:
        return any(s in str(error).lower() for s in [
            "429", "rate limit", "too many requests",
            "suspicious", "locked", "cannot login",
        ])


# ─────────────────────────────────────────────────────────────────────────────
# Account Manager (loads .twitter_accounts.json)
# ─────────────────────────────────────────────────────────────────────────────

def load_accounts(accounts_file: Path | None = None) -> list[dict]:
    """Load Twitter accounts from JSON config file."""
    if accounts_file is None:
        accounts_file = Path(__file__).parent / ".twitter_accounts.json"
    if accounts_file.exists():
        with open(accounts_file) as f:
            return json.load(f)
    return []


def save_accounts(accounts: list[dict], accounts_file: Path | None = None):
    """Save accounts to JSON config file."""
    if accounts_file is None:
        accounts_file = Path(__file__).parent / ".twitter_accounts.json"
    if accounts_file:
        with open(accounts_file, "w") as f:
            json.dump(accounts, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Search Query Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_search_queries(topic: str, focus: str = "all") -> list[str]:
    """
    Build Twitter search queries from a topic string.
    Adds appropriate operators based on the focus area.
    """
    queries = []

    if focus in ("github_repos", "all"):
        queries.append(f"{topic} site:github.com")
        queries.append(f"{topic} github.com")

    if focus in ("trending", "all"):
        queries.append(topic)

    if focus in ("official_updates", "all"):
        pass  # Let official searches use raw topic

    if focus in ("analysis", "all"):
        queries.append(f"{topic} analysis")

    # Fallback: just the raw topic
    if not queries:
        queries.append(topic)

    return queries[:4]  # Max 4 queries to avoid rate limits


# ─────────────────────────────────────────────────────────────────────────────
# Tweet normalizer
# ─────────────────────────────────────────────────────────────────────────────

def normalize_tweet(tweet: Any, search_term: str = "") -> dict:
    """
    Normalize a twscrape Tweet object (or Nitter dict) into a flat dict.
    Works with both authenticated (twscrape) and fallback (Nitter) data.
    """
    result = {
        "search_term": search_term,
        "source": "twscrape",
    }

    # twscrape Tweet object attributes
    if hasattr(tweet, "id"):
        result["id"] = str(tweet.id)
        result["username"] = getattr(tweet.user, "username", "unknown") if hasattr(tweet, "user") else "unknown"
        result["display_name"] = getattr(tweet.user, "name", "") if hasattr(tweet, "user") else ""
        result["text"] = tweet.rawContent or ""
        result["created_at"] = str(tweet.created_at) if tweet.created_at else ""
        result["likes"] = tweet.favorite_count or 0
        result["retweets"] = tweet.retweet_count or 0
        result["replies"] = tweet.reply_count or 0
        result["views"] = tweet.view_count or 0
        result["lang"] = tweet.lang or "en"
        result["has_media"] = bool(tweet.media) if hasattr(tweet, "media") else False

        # Extract URLs from tweet entities
        urls = []
        if hasattr(tweet, "url") and tweet.url:
            urls = [tweet.url] if isinstance(tweet.url, str) else []
        result["urls"] = urls

    # Nitter dict fallback
    elif isinstance(tweet, dict):
        result["id"] = tweet.get("id", "unknown")
        result["username"] = tweet.get("username", "unknown")
        result["display_name"] = tweet.get("display_name", "")
        result["text"] = tweet.get("text", "")
        result["created_at"] = tweet.get("created_at", "")
        result["likes"] = tweet.get("likes", 0)
        result["retweets"] = tweet.get("retweets", 0)
        result["replies"] = tweet.get("replies", 0)
        result["views"] = tweet.get("views", 0)
        result["lang"] = tweet.get("lang", "en")
        result["has_media"] = tweet.get("has_media", False)
        result["source"] = tweet.get("source", "nitter")
        result["urls"] = []

    else:
        result["id"] = "unknown"
        result["username"] = "unknown"
        result["text"] = ""
        result["source"] = "unknown"

    # Extract GitHub links
    all_text = result["text"] + " " + " ".join(result.get("urls", []))
    result["github_repos"] = extract_github_repos(all_text)
    result["has_github_link"] = len(result["github_repos"]) > 0

    # Sentiment
    sent = compute_sentiment(result["text"])
    result["sentiment"] = sent
    result["sentiment_label"] = sentiment_label(sent["bullish"], sent["bearish"], sent["neutral"])

    # Engagement score
    views = max(result.get("views", 1), 1)
    result["engagement_score"] = round(
        (result.get("likes", 0) + result.get("retweets", 0) * 2) / views, 4
    )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Time filtering
# ─────────────────────────────────────────────────────────────────────────────

def filter_by_hours(tweets: list[dict], hours: int) -> list[dict]:
    """Filter tweets to only those within the last N hours."""
    if hours <= 0:
        return tweets

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    filtered = []
    for t in tweets:
        try:
            ts = t.get("created_at", "")
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt >= cutoff:
                    filtered.append(t)
        except Exception:
            filtered.append(t)  # Keep if we can't parse timestamp
    return filtered