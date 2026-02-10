"""Stealth utilities for avoiding detection."""

import random
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Realistic browser User-Agents (updated 2024-2025)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

# Realistic browser headers
def get_browser_headers(referer: Optional[str] = None) -> dict:
    """Get realistic browser headers."""
    ua = random.choice(USER_AGENTS)

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    if referer:
        headers["Referer"] = referer
        headers["Sec-Fetch-Site"] = "same-origin"

    # Add Chrome-specific headers if Chrome UA
    if "Chrome" in ua and "Edg" not in ua:
        headers["Sec-Ch-Ua"] = '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"' if "Windows" in ua else '"macOS"'

    return headers


def get_api_headers() -> dict:
    """Get headers for API requests (JSON)."""
    ua = random.choice(USER_AGENTS)

    return {
        "User-Agent": ua,
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def get_image_headers(referer: str) -> dict:
    """Get headers for image downloads."""
    ua = random.choice(USER_AGENTS)

    return {
        "User-Agent": ua,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "cross-site",
    }


async def random_delay(min_sec: float = 0.5, max_sec: float = 2.0):
    """Wait for a random duration to simulate human behavior."""
    delay = random.uniform(min_sec, max_sec)
    await asyncio.sleep(delay)


async def human_delay():
    """Simulate human-like delay between actions."""
    # Humans are not perfectly random - they have patterns
    # Most delays are short, occasional longer pauses
    if random.random() < 0.1:
        # 10% chance of longer pause (distracted, reading, etc.)
        delay = random.uniform(3.0, 8.0)
    elif random.random() < 0.3:
        # 30% chance of medium pause
        delay = random.uniform(1.5, 3.0)
    else:
        # 60% chance of quick action
        delay = random.uniform(0.5, 1.5)

    await asyncio.sleep(delay)


async def page_delay():
    """Delay between downloading pages (simulates reading/scrolling)."""
    # Shorter delays for pages, but still random
    delay = random.uniform(0.3, 1.2)
    await asyncio.sleep(delay)


async def chapter_delay():
    """Delay between chapters (simulates finishing one and starting another)."""
    # Longer delay between chapters
    delay = random.uniform(2.0, 5.0)
    logger.debug(f"Chapter delay: {delay:.1f}s")
    await asyncio.sleep(delay)


async def rate_limit_backoff(attempt: int):
    """Exponential backoff when rate limited."""
    base_delay = 5.0
    max_delay = 120.0

    # Exponential backoff with jitter
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.3)
    total_delay = delay + jitter

    logger.warning(f"Rate limit backoff: waiting {total_delay:.1f}s (attempt {attempt + 1})")
    await asyncio.sleep(total_delay)


class StealthRateLimiter:
    """Rate limiter with random jitter to avoid patterns."""

    def __init__(self, requests_per_second: float = 2.0, jitter: float = 0.5):
        self.min_interval = 1.0 / requests_per_second
        self.jitter = jitter
        self.last_request = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until it's safe to make a request."""
        async with self._lock:
            import time
            now = time.monotonic()

            # Calculate required wait time
            elapsed = now - self.last_request
            base_wait = self.min_interval - elapsed

            if base_wait > 0:
                # Add random jitter
                jitter = random.uniform(0, self.jitter)
                wait_time = base_wait + jitter
                await asyncio.sleep(wait_time)
            else:
                # Still add small random delay
                await asyncio.sleep(random.uniform(0.1, 0.3))

            self.last_request = time.monotonic()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


# Global stealth rate limiter (more conservative than before)
# 2 requests per second with 0.5s jitter = effectively 1.5-2.5 req/sec
STEALTH_LIMITER = StealthRateLimiter(requests_per_second=2.0, jitter=0.5)
