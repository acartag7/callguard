"""Shared base for HTTP audit sinks — retry, session reuse, timeout.

Note: fire-and-forget mode may silently drop events after exhausting retries.
Provide an ``on_failure`` callback for production use to detect audit gaps.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BASE_DELAY = 1.0
_DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)


class HTTPSinkBase:
    """Base class providing shared aiohttp session, retry, and timeout.

    Subclasses call ``_send_with_retry(url, body, headers)`` in their
    ``emit()`` method.  The session is created lazily on first use and
    reused across calls.  Call ``close()`` to release the connection pool.

    Args:
        on_failure: Optional async callback invoked when all retries are
            exhausted.  Receives ``(body_dict, last_exception)``.
    """

    def __init__(
        self,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        base_delay: float = _DEFAULT_BASE_DELAY,
        timeout: aiohttp.ClientTimeout | None = None,
        on_failure: Callable[[Any, Exception], Awaitable[None]] | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._timeout = timeout or _DEFAULT_TIMEOUT
        self._session: aiohttp.ClientSession | None = None
        self._on_failure = on_failure

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session

    async def _send_with_retry(
        self,
        url: str,
        body: str,
        headers: dict[str, str],
    ) -> None:
        """POST *body* to *url* with exponential-backoff retry."""
        last_error: Exception | None = None
        session = await self._get_session()

        for attempt in range(self._max_retries):
            try:
                async with session.post(url, data=body, headers=headers) as resp:
                    resp.raise_for_status()
                    return
            except Exception as exc:
                last_error = exc
                if attempt < self._max_retries - 1:
                    delay = self._base_delay * (2**attempt)
                    logger.warning(
                        "POST to %s failed (attempt %d/%d): %s. Retrying in %.1fs.",
                        url,
                        attempt + 1,
                        self._max_retries,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)

        logger.error(
            "POST to %s failed after %d retries: %s",
            url,
            self._max_retries,
            last_error,
        )
        if self._on_failure and last_error is not None:
            try:
                await self._on_failure(body, last_error)
            except Exception:
                logger.exception("on_failure callback raised")

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
