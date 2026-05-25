"""
X/Twitter MCP Server — Claude Code Research Integration
Provides 5 research-oriented tools for Twitter/X data collection and analysis.
Designed for: AI agents, crypto AI, Polymarket updates, GitHub repos, emerging tech.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    GetPromptResult,
    PromptMessage,
    ServerResult,
)

from .twitter_research import (
    GitHubClient,
    RateLimiter,
    build_search_queries,
    compute_sentiment,
    extract_github_repos,
    extract_urls,
    filter_by_hours,
    load_accounts,
    normalize_tweet,
    search_via_nitter,
    fetch_user_via_nitter,
)

# ── Logging ────────────────────────────────────────────────────────────────────
log = logging.getLogger("twitter_mcp")
log.addHandler(logging.NullHandler())


# ── Config ────────────────────────────────────────────────────────────────────
ACCOUNTS_FILE = Path(__file__).parent / ".twitter_accounts.json"
COOKIES_FILE = Path(__file__).parent / ".twitter_cookies.json"
DATA_DIR = Path(__file__).parent.parent.parent / "data"


# ── twscrape helpers ───────────────────────────────────────────────────────────

async def _get_twscrape_api() -> Any | None:
    """Get a twscrape API instance with active credentials. Returns None if no accounts."""
    accounts = load_accounts()
    if not accounts:
        return None

    try:
        from twscrape.accounts_pool import AccountsPool
        from twscrape.api import API

        pool = AccountsPool()
        for acc in accounts:
            await pool.add_account(
                username=acc["username"],
                password=acc["password"],
                email=acc.get("email", ""),
                email_password=acc.get("email_password", ""),
                cookies=acc.get("cookies"),
                proxy=acc.get("proxy"),
            )

        await pool.login_all()
        return API(pool)

    except Exception as e:
        log.warning(f"twscrape unavailable: {e}")
        return None


async def _search_with_twscrape(query: str, limit: int) -> list[dict]:
    """Search using twscrape with full API access."""
    api = await _get_twscrape_api()
    if not api:
        return []

    results = []
    rate_limiter = RateLimiter()

    try:
        async for tweet in api.search(query, limit=limit):
            if not tweet:
                continue
            await rate_limiter.wait("search")
            results.append(normalize_tweet(tweet, search_term=query))
        await _cleanup_api(api)
    except Exception as e:
        log.error(f"twscrape search failed: {e}")

    return results


async def _get_user_tweets_with_twscrape(username: str, limit: int) -> list[dict]:
    """Get user tweets via twscrape."""
    api = await _get_twscrape_api()
    if not api:
        return []

    results = []
    try:
        user = await api.user_by_login(username)
        if not user:
            return []

        async for tweet in api.user_tweets(user.id, limit=limit):
            if not tweet:
                continue
            results.append(normalize_tweet(tweet, search_term=f"@{username}"))
        await _cleanup_api(api)
    except Exception as e:
        log.error(f"twscrape user tweets failed for {username}: {e}")

    return results


async def _get_tweet_thread(tweet_id: str) -> list[dict]:
    """Get full thread for a tweet via twscrape."""
    api = await _get_twscrape_api()
    if not api:
        return []

    results = []
    try:
        async for tweet in api.tweet_thread(int(tweet_id), limit=20):
            if tweet:
                results.append(normalize_tweet(tweet))
        await _cleanup_api(api)
    except Exception as e:
        log.error(f"twscrape thread failed for {tweet_id}: {e}")

    return results


async def _cleanup_api(api: Any):
    """Clean up API/pool resources."""
    try:
        if hasattr(api, "pool"):
            await api.pool.cleanup()
    except Exception:
        pass


def _parse_tweet_id_from_url(url: str) -> str | None:
    """Extract tweet ID from a Twitter/X URL."""
    patterns = [
        r'x\.com/\w+/status/(\d+)',
        r'twitter\.com/\w+/status/(\d+)',
        r'x\.com/\w+/statuses/(\d+)',
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


# ── GitHub Client ───────────────────────────────────────────────────────────────

_github = GitHubClient()


# ── MCP Server ────────────────────────────────────────────────────────────────

APP = Server(
    name="twitter-research",
    version="2.0.0",
)


@APP.list_tools()
async def list_tools() -> list[Tool]:
    """Expose 5 research tools to Claude Code."""
    return [
        Tool(
            name="fetch_tweet_from_url",
            description="Given a Twitter/X URL, fetch the full tweet content including thread context, extract all links (GitHub repos, websites), and return structured data with sentiment analysis. Use this when a user pastes a Twitter link — it will fetch the full content, extract linked GitHub repos and websites, and summarize the thread.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full Twitter/X URL like https://x.com/sama/status/123456789",
                    },
                    "include_thread": {
                        "type": "boolean",
                        "description": "Fetch the full thread this tweet belongs to (default: true)",
                        "default": True,
                    },
                },
                "required": ["url"],
            },
        ),
        Tool(
            name="search_twitter_research",
            description="Research-oriented Twitter search for AI agents, crypto AI, Polymarket, GitHub repos, and emerging tech. Builds smart search queries with Twitter operators (site:github.com, from:, since:), extracts GitHub links, and ranks by engagement. Use this when asked to research a topic from Twitter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Research topic (e.g., 'AI agent framework 2025', 'crypto AI trading bot github', 'Polymarket new features', 'headless agent')",
                    },
                    "focus": {
                        "type": "string",
                        "enum": ["github_repos", "trending", "official_updates", "analysis", "all"],
                        "default": "all",
                        "description": "Filter search focus: github_repos (GitHub links only), trending (most engaged), official_updates (from official accounts), analysis (in-depth discussion), all (default)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max tweets to return (default: 15, max: 50)",
                        "default": 15,
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Only tweets within last N hours (default: 168 = 1 week)",
                        "default": 168,
                    },
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="get_polymarket_official",
            description="Monitor Polymarket official accounts for product updates, API changes, new market features, and announcements. Use for staying current on Polymarket developments.",
            inputSchema={
                "type": "object",
                "properties": {
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["PolymarketAG", "Polymarket", "thiomark"],
                        "description": "Twitter usernames to monitor (without @)",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Look back N hours (default: 48)",
                        "default": 48,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max tweets per account (default: 20)",
                        "default": 20,
                    },
                },
            },
        ),
        Tool(
            name="track_ai_researchers",
            description="Monitor key AI researchers, labs, and projects for new releases, papers, frameworks, and GitHub repos. Configurable account list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "accounts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["sama", "ylecun", "kabornilab", "AndrewYNg", "hardmaru", "kaborin", "jimfan"],
                        "description": "Twitter usernames to track (without @)",
                    },
                    "hours": {
                        "type": "integer",
                        "description": "Look back N hours (default: 48)",
                        "default": 48,
                    },
                    "filter_github": {
                        "type": "boolean",
                        "description": "Only return tweets with GitHub links (default: false)",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max tweets per account (default: 15)",
                        "default": 15,
                    },
                },
            },
        ),
        Tool(
            name="extract_github_metadata",
            description="Given a GitHub repo in 'owner/repo' format, fetch repo metadata: description, stars, language, topics, README preview, recent commits. No auth needed. Use this to research linked GitHub repos from Twitter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo": {
                        "type": "string",
                        "description": "GitHub repo in 'owner/repo' format (e.g., 'anthropic/anthropic-cookbook')",
                    },
                    "include_readme": {
                        "type": "boolean",
                        "description": "Include README content (first 2000 chars)",
                        "default": False,
                    },
                },
                "required": ["repo"],
            },
        ),
    ]


@APP.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Route tool calls to implementations."""

    # ── fetch_tweet_from_url ──────────────────────────────────────────────────
    if name == "fetch_tweet_from_url":
        url = arguments.get("url", "")
        include_thread = arguments.get("include_thread", True)

        if not url:
            return [TextContent(type="text", text="Error: URL is required")]

        tweet_id = _parse_tweet_id_from_url(url)
        if not tweet_id:
            return [TextContent(type="text", text=f"Error: Could not parse tweet ID from URL: {url}")]

        result = {"url": url, "tweet_id": tweet_id}

        # Try twscrape first (authenticated)
        tweets = await _get_tweet_thread(tweet_id) if include_thread else []
        if not tweets:
            # Try fetching single tweet via search
            tweets = await _search_with_twscrape(f"url:{tweet_id}", limit=3)

        if not tweets:
            # Fallback: Nitter
            tweets = await search_via_nitter(f"url:{tweet_id}", limit=3)

        if tweets:
            main_tweet = tweets[0]
            result["tweet"] = main_tweet
            result["thread_length"] = len(tweets)
            result["thread_tweets"] = tweets[1:5] if len(tweets) > 1 else []

            # Enrich with GitHub metadata
            if main_tweet.get("github_repos"):
                enriched = []
                for repo in main_tweet["github_repos"][:3]:
                    meta = await _github.fetch_repo(repo["owner"], repo["repo"])
                    if meta:
                        enriched.append(meta)
                result["github_repos_enriched"] = enriched
        else:
            result["error"] = "Could not fetch tweet — check URL or add Twitter credentials"

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    # ── search_twitter_research ───────────────────────────────────────────────
    elif name == "search_twitter_research":
        topic = arguments.get("topic", "")
        focus = arguments.get("focus", "all")
        limit = min(arguments.get("limit", 15), 50)
        hours = arguments.get("hours", 168)

        if not topic:
            return [TextContent(type="text", text="Error: topic is required")]

        queries = build_search_queries(topic, focus)
        all_tweets = []
        used_queries = []

        for query in queries[:3]:
            await asyncio.sleep(1)  # Small delay between queries
            if _has_twitter_credentials():
                tweets = await _search_with_twscrape(query, limit=limit)
            else:
                tweets = await search_via_nitter(query, limit=limit)

            if tweets:
                for t in tweets:
                    t["search_term"] = query
                all_tweets.extend(tweets)
                used_queries.append(query)

        # Deduplicate by ID
        seen = set()
        unique = []
        for t in all_tweets:
            tid = t.get("id", "")
            if tid not in seen:
                seen.add(tid)
                unique.append(t)

        # Filter by time
        unique = filter_by_hours(unique, hours)

        # Extract GitHub repos across all tweets
        github_repos_found = {}
        for t in unique:
            for repo in t.get("github_repos", []):
                key = repo["full_name"]
                if key not in github_repos_found:
                    github_repos_found[key] = repo

        # Enrich top GitHub repos
        github_enriched = []
        for key in list(github_repos_found.keys())[:5]:
            owner, repo = key.split("/", 1)
            meta = await _github.fetch_repo(owner, repo)
            if meta and "error" not in meta:
                github_enriched.append(meta)
            await asyncio.sleep(0.5)  # Rate limit protection

        # Sort tweets by engagement
        unique.sort(key=lambda t: t.get("engagement_score", 0), reverse=True)
        tweets_ranked = unique[:limit]

        # Sentiment summary
        total_b, total_be, total_n = 0, 0, 0
        for t in tweets_ranked:
            s = t.get("sentiment", {})
            total_b += s.get("bullish", 0)
            total_be += s.get("bearish", 0)
            total_n += s.get("neutral", 0)

        result = {
            "topic": topic,
            "focus": focus,
            "queries_used": used_queries,
            "total_tweets_found": len(unique),
            "tweets_returned": len(tweets_ranked),
            "github_repos_found": len(github_repos_found),
            "github_repos": github_enriched,
            "top_tweets": tweets_ranked[:5],
            "sentiment_summary": {
                "bullish": total_b,
                "bearish": total_be,
                "neutral": total_n,
                "label": "BULLISH" if total_b > total_be * 1.5 else "BEARISH" if total_be > total_b * 1.5 else "NEUTRAL",
            },
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    # ── get_polymarket_official ───────────────────────────────────────────────
    elif name == "get_polymarket_official":
        accounts = arguments.get("accounts", ["PolymarketAG", "Polymarket", "thiomark"])
        hours = arguments.get("hours", 48)
        limit = min(arguments.get("limit", 20), 30)

        all_updates = []
        for username in accounts:
            await asyncio.sleep(1)
            if _has_twitter_credentials():
                tweets = await _get_user_tweets_with_twscrape(username, limit=limit)
            else:
                tweets = await fetch_user_via_nitter(username, limit=limit)

            tweets = filter_by_hours(tweets, hours)
            for t in tweets:
                t["account"] = username
            all_updates.extend(tweets)

        # Sort by engagement
        all_updates.sort(key=lambda t: t.get("engagement_score", 0), reverse=True)

        # Extract GitHub links
        github_repos = []
        for t in all_updates:
            for repo in t.get("github_repos", []):
                if repo["full_name"] not in [g.get("full_name") for g in github_repos]:
                    github_repos.append(repo)

        result = {
            "accounts_monitored": accounts,
            "hours_looked_back": hours,
            "total_updates": len(all_updates),
            "updates": all_updates,
            "github_links_found": len(github_repos),
            "github_repos": github_repos[:5],
            "auth_mode": "twscrape" if _has_twitter_credentials() else "nitter_fallback",
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    # ── track_ai_researchers ──────────────────────────────────────────────────
    elif name == "track_ai_researchers":
        accounts = arguments.get("accounts", ["sama", "ylecun", "kabornilab", "AndrewYNg", "hardmaru", "kaborin", "jimfan"])
        hours = arguments.get("hours", 48)
        filter_github = arguments.get("filter_github", False)
        limit = min(arguments.get("limit", 15), 30)

        all_tweets = []
        for username in accounts:
            await asyncio.sleep(1)
            if _has_twitter_credentials():
                tweets = await _get_user_tweets_with_twscrape(username, limit=limit)
            else:
                tweets = await fetch_user_via_nitter(username, limit=limit)

            tweets = filter_by_hours(tweets, hours)
            if filter_github:
                tweets = [t for t in tweets if t.get("has_github_link", False)]

            for t in tweets:
                t["account"] = username
            all_tweets.extend(tweets)

        # Sort by engagement
        all_tweets.sort(key=lambda t: t.get("engagement_score", 0), reverse=True)

        # Extract GitHub repos
        github_repos = {}
        for t in all_tweets:
            for repo in t.get("github_repos", []):
                key = repo["full_name"]
                if key not in github_repos:
                    github_repos[key] = repo

        # Enrich top repos
        github_enriched = []
        for key in list(github_repos.keys())[:5]:
            owner, repo = key.split("/", 1)
            meta = await _github.fetch_repo(owner, repo)
            if meta and "error" not in meta:
                github_enriched.append(meta)
            await asyncio.sleep(0.5)

        result = {
            "accounts_tracked": accounts,
            "hours_looked_back": hours,
            "filter_github_only": filter_github,
            "total_tweets": len(all_tweets),
            "tweets": all_tweets,
            "github_repos_found": len(github_repos),
            "github_repos": github_enriched,
            "auth_mode": "twscrape" if _has_twitter_credentials() else "nitter_fallback",
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    # ── extract_github_metadata ───────────────────────────────────────────────
    elif name == "extract_github_metadata":
        repo_str = arguments.get("repo", "")
        include_readme = arguments.get("include_readme", False)

        if not repo_str:
            return [TextContent(type="text", text="Error: repo is required (format: owner/repo)")]

        # Parse owner/repo
        parts = repo_str.strip("/").split("/")
        if len(parts) != 2:
            return [TextContent(type="text", text=f"Error: invalid repo format '{repo_str}'. Use 'owner/repo' format.")]

        owner, repo = parts[0], parts[1]
        meta = await _github.fetch_repo(owner, repo, include_readme=include_readme)

        if not meta:
            return [TextContent(type="text", text=f"Error: Repo '{owner}/{repo}' not found or inaccessible.")]

        if "error" in meta:
            return [TextContent(type="text", text=json.dumps({"error": meta["error"], "repo": meta.get("repo", "")}, indent=2))]

        return [TextContent(type="text", text=json.dumps(meta, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _has_twitter_credentials() -> bool:
    """Check if Twitter credentials are configured."""
    accounts = load_accounts()
    return len(accounts) > 0


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    """Run the MCP server over stdio."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    log.info("Twitter Research MCP server starting...")

    async with stdio_server() as (read_stream, write_stream):
        await APP.run(read_stream, write_stream, APP.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())