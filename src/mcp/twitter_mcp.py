"""
X/Twitter MCP Server — BTC Predictor Research Layer
Provides Twitter/X data to the multi-agent system for sentiment and trend analysis.
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

# ── Logging ────────────────────────────────────────────────────────────────────
log = logging.getLogger("twitter_mcp")
log.addHandler(logging.NullHandler())


# ── twscrape helpers ────────────────────────────────────────────────────────────
TWITTER_COOKIES_FILE = Path(__file__).parent / ".twitter_cookies.json"
TWITTER_ACCOUNTS_FILE = Path(__file__).parent / ".twitter_accounts.json"


async def load_accounts() -> list[dict]:
    """Load Twitter accounts from JSON config."""
    if TWITTER_ACCOUNTS_FILE.exists():
        with open(TWITTER_ACCOUNTS_FILE) as f:
            return json.load(f)
    return []


async def search_tweets_via_api(query: str, limit: int = 20) -> list[dict]:
    """
    Search tweets using twscrape's API.
    Falls back tohttpx direct scraping if no account available.
    """
    try:
        from twscrape.accounts_pool import AccountsPool, InvalidPasswordError
        from twscrape.api import API

        accounts = await load_accounts()
        if not accounts:
            log.warning("No Twitter accounts configured — using fallback scraping")
            return await _fallback_search(query, limit)

        pool = AccountsPool()
        for acc in accounts:
            try:
                await pool.add_account(
                    username=acc["username"],
                    password=acc["password"],
                    email=acc.get("email", ""),
                    cookies=acc.get("cookies"),
                )
            except InvalidPasswordError:
                log.warning(f"Failed to add account {acc['username']}")

        api = API(pool)

        tweet_results = []
        async for tweet in api.search_tweets(query, limit=limit):
            tweet_data = {
                "id": tweet.id,
                "url": f"https://x.com/{tweet.user.username}/status/{tweet.id}",
                "username": tweet.user.username,
                "display_name": tweet.user.name,
                "text": tweet.rawContent,
                "created_at": str(tweet.created_at) if tweet.created_at else "",
                "likes": tweet.favorite_count or 0,
                "retweets": tweet.retweet_count or 0,
                "replies": tweet.reply_count or 0,
                "views": tweet.view_count or 0,
                "is_retweet": bool(tweet.note_tweet),
                "lang": tweet.lang or "en",
                "has_media": bool(tweet.media),
            }
            tweet_results.append(tweet_data)

        await pool.cleanup()
        return tweet_results

    except Exception as e:
        log.error(f"Twitter search failed: {e}")
        return await _fallback_search(query, limit)


async def _fallback_search(query: str, limit: int) -> list[dict]:
    """
    Fallback: use Nitter RSS / public APIs for basic tweet search.
    Works without Twitter credentials.
    """
    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            encoded = query.replace(" ", "%20")
            url = f"https://nitter.net/search?f=tweets&q={encoded}"
            resp = await client.get(url)
            if resp.status_code == 200:
                results = _parse_nitter_html(resp.text, limit)
    except Exception as e:
        log.warning(f"Fallback search also failed: {e}")

    return results


def _parse_nitter_html(html: str, limit: int) -> list[dict]:
    """Parse tweets from Nitter RSS HTML."""
    import re
    tweets = []
    pattern = re.compile(
        r'<div class="tweet-content[^"]*">(.*?)</div>',
        re.DOTALL | re.IGNORECASE,
    )
    matches = pattern.findall(html)
    for i, match in enumerate(matches[:limit]):
        clean = re.sub(r"<[^>]+>", " ", match).strip()
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if clean:
            tweets.append({
                "id": f"nitter_{i}",
                "text": clean[:500],
                "username": "unknown",
                "source": "nitter_fallback",
            })
    return tweets


async def get_user_tweets(username: str, limit: int = 20) -> list[dict]:
    """Get recent tweets from a specific user."""
    try:
        from twscrape.accounts_pool import AccountsPool
        from twscrape.api import API

        accounts = await load_accounts()
        if not accounts:
            return []

        pool = AccountsPool()
        for acc in accounts:
            await pool.add_account(
                username=acc["username"],
                password=acc["password"],
                email=acc.get("email", ""),
            )
        api = API(pool)
        results = []
        async for tweet in api.user_tweets(username, limit=limit):
            results.append({
                "id": tweet.id,
                "url": f"https://x.com/{username}/status/{tweet.id}",
                "text": tweet.rawContent[:500] if tweet.rawContent else "",
                "created_at": str(tweet.created_at) if tweet.created_at else "",
                "likes": tweet.favorite_count or 0,
                "retweets": tweet.retweet_count or 0,
            })
        await pool.cleanup()
        return results
    except Exception as e:
        log.error(f"Get user tweets failed: {e}")
        return []


async def get_trending_topics() -> list[dict]:
    """Get currently trending topics on Twitter/X."""
    try:
        from twscrape.accounts_pool import AccountsPool
        from twscrape.api import API

        accounts = await load_accounts()
        if not accounts:
            return []

        pool = AccountsPool()
        for acc in accounts:
            await pool.add_account(
                username=acc["username"],
                password=acc["password"],
                email=acc.get("email", ""),
            )
        api = API(pool)
        trends = await api.trending()
        await pool.cleanup()
        return [
            {
                "name": t.name,
                "domain": t.domain,
                "meta_description": t.meta_description,
                "tweet_count": t.tweet_count,
            }
            for t in (trends or [])
        ]
    except Exception as e:
        log.error(f"Get trending failed: {e}")
        return []


# ── BTC/Crypto specific search helpers ───────────────────────────────────────

async def search_crypto_tweets(query: str, limit: int = 30) -> list[dict]:
    """
    Search for crypto/BTC-related tweets, sorted by engagement.
    Adds crypto-specific signal scoring.
    """
    search_terms = [
        f"{query} bitcoin",
        f"{query} BTC",
        f"bitcoin {query}",
        "$BTC",
    ]

    all_tweets = []
    for term in search_terms[:2]:  # Limit to avoid rate limits
        tweets = await search_tweets_via_api(term, limit=limit // 2)
        for t in tweets:
            t["search_term"] = term
        all_tweets.extend(tweets)

    # Deduplicate by ID
    seen = set()
    unique = []
    for t in all_tweets:
        tid = t.get("id", "")
        if tid not in seen:
            seen.add(tid)
            unique.append(t)

    # Add engagement score
    for t in unique:
        likes = t.get("likes", 0)
        rts = t.get("retweets", 0)
        views = t.get("views", max(likes + rts, 1))
        t["engagement_score"] = round((likes + rts * 2) / max(views, 1), 4)
        t["sentiment_keywords"] = _extract_sentiment_keywords(t.get("text", ""))

    return unique[:limit]


def _extract_sentiment_keywords(text: str) -> dict[str, int]:
    """Extract crypto sentiment keywords from tweet text."""
    text_lower = text.lower()
    bullish = ["bullish", "long", "buy", "accumulate", "breakout", "moon", "pump", "up", "green", "support", "dip buy", "call"]
    bearish = ["bearish", "short", "sell", "drop", "breakdown", "crash", "dump", "down", "red", "resistance", "liquidat"]
    neutral = ["neutral", "watch", "wait", "range", "sideways"]

    counts = {"bullish": 0, "bearish": 0, "neutral": 0}
    for kw in bullish:
        if kw in text_lower:
            counts["bullish"] += 1
    for kw in bearish:
        if kw in text_lower:
            counts["bearish"] += 1
    for kw in neutral:
        if kw in text_lower:
            counts["neutral"] += 1

    return counts


# ── MCP Server ────────────────────────────────────────────────────────────────

APP = Server(
    name="twitter-mcp",
    version="1.0.0",
)


@APP.list_tools()
async def list_tools() -> list[Tool]:
    """Expose Twitter tools to Claude Code."""
    return [
        Tool(
            name="search_crypto_tweets",
            description="Search for crypto/BTC-related tweets. Returns tweets with engagement scores and sentiment keywords. Use this to research market sentiment, whale activity, and emerging narratives.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'bitcoin ETF', 'BTC bull', 'ethereum merge')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of tweets to return (default: 20, max: 50)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_tweets",
            description="General Twitter/X search. Returns tweets matching any query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max tweets (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_user_tweets",
            description="Get recent tweets from a specific Twitter/X user. Useful for following specific analysts, traders, or news accounts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Twitter username without @ (e.g., 'cz_binance')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent tweets to fetch (default: 10)",
                        "default": 10,
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="get_trending_crypto",
            description="Get currently trending topics on Twitter/X. Filter for crypto-related trends. Useful for detecting emerging narratives and market关注的热点.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="analyze_sentiment_batch",
            description="Analyze a batch of tweets and produce a sentiment summary. Extracts bullish/bearish/neutral signals from tweet text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tweets": {
                        "type": "array",
                        "description": "Array of tweet objects with 'text' field",
                    },
                },
                "required": ["tweets"],
            },
        ),
    ]


@APP.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Execute a Twitter MCP tool."""
    if name == "search_crypto_tweets":
        query = arguments.get("query", "")
        limit = min(arguments.get("limit", 20), 50)
        tweets = await search_crypto_tweets(query, limit)
        return [TextContent(
            type="text",
            text=json.dumps({"tweets": tweets, "count": len(tweets)}, indent=2),
        )]

    elif name == "search_tweets":
        query = arguments.get("query", "")
        limit = min(arguments.get("limit", 20), 50)
        tweets = await search_tweets_via_api(query, limit)
        return [TextContent(
            type="text",
            text=json.dumps({"tweets": tweets, "count": len(tweets)}, indent=2),
        )]

    elif name == "get_user_tweets":
        username = arguments.get("username", "")
        limit = min(arguments.get("limit", 10), 50)
        if not username:
            return [TextContent(type="text", text="Error: username required")]
        tweets = await get_user_tweets(username, limit)
        return [TextContent(
            type="text",
            text=json.dumps({"username": username, "tweets": tweets, "count": len(tweets)}, indent=2),
        )]

    elif name == "get_trending_crypto":
        trends = await get_trending_topics()
        crypto_filtered = [t for t in trends if any(
            kw in t.get("name", "").lower() or kw in t.get("meta_description", "").lower()
            for kw in ["bitcoin", "btc", "crypto", "eth", "sol", "bnb", "xrp", "dogecoin", "trump", "crypto", "coin"]
        )]
        return [TextContent(
            type="text",
            text=json.dumps({"all_trends": trends, "crypto_trends": crypto_filtered, "count": len(trends)}, indent=2),
        )]

    elif name == "analyze_sentiment_batch":
        tweets = arguments.get("tweets", [])
        if not tweets:
            return [TextContent(type="text", text="No tweets provided")]

        total_bullish = 0
        total_bearish = 0
        total_neutral = 0
        total_engagement = 0.0
        samples = []

        for t in tweets:
            text = t.get("text", "")
            keywords = _extract_sentiment_keywords(text)
            total_bullish += keywords["bullish"]
            total_bearish += keywords["bearish"]
            total_neutral += keywords["neutral"]
            total_engagement += t.get("engagement_score", 0)
            if len(samples) < 3:
                samples.append({"text": text[:200], "keywords": keywords})

        n = max(len(tweets), 1)
        summary = {
            "tweet_count": n,
            "avg_engagement": round(total_engagement / n, 4),
            "sentiment": {
                "bullish_signals": total_bullish,
                "bearish_signals": total_bearish,
                "neutral_signals": total_neutral,
                "net_sentiment": total_bullish - total_bearish,
            },
            "sentiment_label": (
                "BULLISH" if total_bullish > total_bearish * 1.5
                else "BEARISH" if total_bearish > total_bullish * 1.5
                else "NEUTRAL"
            ),
            "sample_tweets": samples,
        }
        return [TextContent(type="text", text=json.dumps(summary, indent=2))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    """Run the MCP server over stdio."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "WARNING"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    async with stdio_server() as (read_stream, write_stream):
        await APP.run(read_stream, write_stream, APP.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())