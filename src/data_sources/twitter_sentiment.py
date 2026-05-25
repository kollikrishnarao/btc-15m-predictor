"""
Twitter/X Sentiment Data Source.
Fetches live crypto tweets via twscrape and produces a structured sentiment score.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class TwitterSentimentResult:
    """Result of Twitter sentiment analysis."""
    score: float = 0.5          # 0.0 = bearish, 0.5 = neutral, 1.0 = bullish
    confidence: float = 0.3     # How reliable this signal is
    tweet_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    engagement_rate: float = 0.0
    fetched_at: Optional[datetime] = None
    error: Optional[str] = None
    source: str = "twitter"


async def fetch_twitter_sentiment(
    search_terms: list[str] | None = None,
    limit: int = 20,
    timeout: float = 15.0,
) -> TwitterSentimentResult:
    """
    Fetch crypto tweets and compute a sentiment score.

    Args:
        search_terms: list of search queries (default: BTC-related terms)
        limit: max tweets per search term
        timeout: seconds before giving up

    Returns:
        TwitterSentimentResult with score ∈ [0, 1]
    """
    if search_terms is None:
        search_terms = ["bitcoin", "$BTC", "BTC bullish", "BTC bearish"]

    result = TwitterSentimentResult()

    try:
        tweets = await _search_crypto_tweets(search_terms, limit)
        result.tweet_count = len(tweets)

        if not tweets:
            return result

        # Compute sentiment from keyword counts
        total_bullish = sum(1 for t in tweets if _is_bullish(t))
        total_bearish = sum(1 for t in tweets if _is_bearish(t))
        total_neutral = sum(1 for t in tweets if _is_neutral(t))

        result.bullish_count = total_bullish
        result.bearish_count = total_bearish
        result.neutral_count = total_neutral

        n = max(len(tweets), 1)

        # Weighted score: bullish vs bearish ratio
        # score > 0.5 means bullish sentiment
        raw = (total_bullish - total_bearish) / n  # ∈ [-1, 1]
        result.score = round((raw + 1) / 2, 3)     # ∈ [0, 1]

        # Confidence based on tweet count and consensus
        result.confidence = round(min(0.85, 0.25 + 0.05 * min(n, 12)), 3)

        # Engagement rate as secondary signal
        total_engagement = sum(
            t.get("likes", 0) + t.get("retweets", 0)
            for t in tweets
        )
        result.engagement_rate = round(total_engagement / n / 1000, 3)

        result.fetched_at = datetime.now(timezone.utc)

        log.debug(
            f"Twitter sentiment: {result.tweet_count} tweets, "
            f"score={result.score:.3f}, bullish={total_bullish}, bearish={total_bearish}"
        )

    except asyncio.TimeoutError:
        result.error = "Timeout fetching tweets"
        log.warning(result.error)
    except Exception as e:
        result.error = str(e)
        log.warning(f"Twitter sentiment fetch failed: {e}")

    return result


async def _search_crypto_tweets(
    search_terms: list[str],
    limit_per_term: int,
) -> list[dict]:
    """Search for crypto tweets using twscrape or Nitter fallback."""
    try:
        from twscrape.accounts_pool import AccountsPool
        from twscrape.api import API

        accounts = await _load_accounts()
        if not accounts:
            return await _fallback_search(search_terms, limit_per_term)

        pool = AccountsPool()
        for acc in accounts:
            await pool.add_account(
                username=acc["username"],
                password=acc["password"],
                email=acc.get("email", ""),
                cookies=acc.get("cookies"),
            )

        api = API(pool)
        all_tweets = []

        for term in search_terms[:2]:  # Avoid rate limits
            async for tweet in api.search_tweets(term, limit=limit_per_term):
                if not tweet:  # Skip None (promoted/sponsored tweets)
                    continue
                all_tweets.append({
                    "text": tweet.rawContent or "",
                    "likes": tweet.favorite_count or 0,
                    "retweets": tweet.retweet_count or 0,
                    "views": tweet.view_count or 0,
                    "lang": tweet.lang or "en",
                })

        await pool.cleanup()
        return all_tweets

    except Exception as e:
        log.debug(f"twscrape unavailable, using Nitter fallback: {e}")
        return await _fallback_search(search_terms, limit_per_term)


async def _load_accounts() -> list[dict]:
    """Load Twitter accounts from JSON config."""
    import json
    from pathlib import Path
    accounts_file = Path(__file__).parent / ".twitter_accounts.json"
    if accounts_file.exists():
        with open(accounts_file) as f:
            return json.load(f)
    return []


async def _fallback_search(
    search_terms: list[str],
    limit: int,
) -> list[dict]:
    """Fallback via Nitter RSS when no Twitter credentials are configured."""
    import httpx
    import re

    results = []
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for term in search_terms[:1]:  # Single term for fallback
                encoded = term.replace(" ", "%20")
                url = f"https://nitter.net/search?f=tweets&q={encoded}"
                resp = await client.get(url)
                if resp.status_code == 200:
                    tweets = _parse_nitter_html(resp.text, limit)
                    results.extend(tweets)
    except Exception as e:
        log.debug(f"Nitter fallback also failed: {e}")

    return results


def _parse_nitter_html(html: str, limit: int) -> list[dict]:
    """Parse tweets from Nitter search HTML."""
    tweets = []
    pattern = _html_tag_re()
    matches = pattern.findall(html)
    for match in matches[:limit]:
        clean = re.sub(r"<[^>]+>", " ", match).strip()
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        if len(clean) > 10:
            tweets.append({"text": clean[:500]})
    return tweets


def _html_tag_re():
    import re
    return re.compile(r'<div class="tweet-content[^"]*">(.*?)</div>', re.DOTALL | re.IGNORECASE)


# ── Sentiment Keywords ─────────────────────────────────────────────────────────

_BULLISH = {"bullish", "long", "buy", "accumulate", "breakout", "moon", "pump",
            "up", "green", "support", "dip", "call", "long", "hodl", "btfd"}
_BEARISH = {"bearish", "short", "sell", "drop", "breakdown", "crash", "dump",
           "down", "red", "resistance", "liquidat", "sell", "rekt"}
_NEUTRAL = {"neutral", "watch", "wait", "range", "sideways", "uncertain"}


def _is_bullish(tweet: dict) -> bool:
    text = tweet.get("text", "").lower()
    return any(kw in text for kw in _BULLISH)


def _is_bearish(tweet: dict) -> bool:
    text = tweet.get("text", "").lower()
    return any(kw in text for kw in _BEARISH)


def _is_neutral(tweet: dict) -> bool:
    text = tweet.get("text", "").lower()
    return any(kw in text for kw in _NEUTRAL)


def twitter_score_to_sentiment_range(twitter_score: float) -> float:
    """
    Convert Twitter sentiment score (0-1) to a sentiment bias adjustment.
    Returns a value from -0.15 to +0.15 that can be added to the base score.
    """
    # Center at 0.5, scale to ±0.15
    bias = (twitter_score - 0.5) * 0.30
    return max(-0.15, min(0.15, bias))