"""Web image crawler source — fetch images from web search and APIs.

Requires: ``pip install httpx Pillow``

Example::

    source = WebSource(
        queries=["AI generated landscape", "digital art portrait"],
        label=Label.AI_GENERATED,
        max_items=100,
    )
    async for item in source.fetch():
        print(item.label, len(item.content))
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
from collections.abc import AsyncIterator

import httpx

from pykit_dataset.model import DataItem, Label, MediaType

logger = logging.getLogger(__name__)


class WebSource:
    """Fetch images from DuckDuckGo image search.

    No API key required. Uses DuckDuckGo's image API with vqd token.
    """

    def __init__(
        self,
        queries: list[str],
        label: Label,
        max_per_query: int = 50,
    ) -> None:
        self._queries = queries
        self._label = label
        self._max_per_query = max_per_query

    @property
    def name(self) -> str:
        return "web:duckduckgo"

    async def fetch(self) -> AsyncIterator[DataItem]:
        """Search and download images from DuckDuckGo."""
        seen: set[str] = set()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; DatasetBot/1.0)"},
        ) as client:
            for query in self._queries:
                count = 0
                try:
                    urls = await self._search(client, query)
                except Exception:
                    logger.warning("Search failed for query: %s", query, exc_info=True)
                    continue

                for url in urls:
                    if count >= self._max_per_query:
                        break

                    url_hash = hashlib.md5(url.encode()).hexdigest()
                    if url_hash in seen:
                        continue
                    seen.add(url_hash)

                    try:
                        resp = await client.get(url, timeout=15.0)
                        if resp.status_code != 200:
                            continue
                        content_type = resp.headers.get("content-type", "")
                        if "image" not in content_type:
                            continue

                        content = resp.content
                        if len(content) < 1000:
                            continue

                        # Validate it's a real image
                        from PIL import Image

                        img = Image.open(io.BytesIO(content))
                        img.verify()

                        ext = ".jpg" if "jpeg" in content_type else ".png"
                        count += 1

                        yield DataItem(
                            content=content,
                            label=self._label,
                            media_type=MediaType.IMAGE,
                            source_name=self.name,
                            extension=ext,
                            metadata={"query": query, "url": url},
                        )
                    except Exception:
                        continue

                logger.info("  query '%s': %d images", query, count)

    async def _search(self, client: httpx.AsyncClient, query: str) -> list[str]:
        """Get image URLs from DuckDuckGo."""
        # Get vqd token
        resp = await client.get("https://duckduckgo.com/", params={"q": query})
        match = re.search(r"vqd=([\d-]+)", resp.text)
        if not match:
            return []

        vqd = match.group(1)
        api_resp = await client.get(
            "https://duckduckgo.com/i.js",
            params={"q": query, "vqd": vqd, "o": "json", "p": "1", "s": "0"},
        )
        if api_resp.status_code != 200:
            return []

        data = api_resp.json()
        return [r["image"] for r in data.get("results", []) if "image" in r]
