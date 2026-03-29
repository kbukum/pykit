"""Tests for HuggingFace and Web sources with mocked external dependencies."""

from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pykit_dataset.model import Label, MediaType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rgb_jpeg_bytes(width: int = 4, height: int = 4) -> bytes:
    """Create valid JPEG bytes via PIL, guaranteed > 1000 bytes for web tests."""
    import random

    from PIL import Image

    random.seed(0)
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for x in range(width):
        for y in range(height):
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_pil_image(width: int = 4, height: int = 4):
    from PIL import Image

    return Image.new("RGB", (width, height), color=(0, 255, 0))


# ===========================================================================
# HuggingFaceSource tests
# ===========================================================================


class TestHuggingFaceSourceConfig:
    def test_defaults(self):
        from pykit_dataset.sources.huggingface import HuggingFaceSourceConfig

        cfg = HuggingFaceSourceConfig(repo="owner/dataset")
        assert cfg.repo == "owner/dataset"
        assert cfg.split == "train"
        assert cfg.image_col == "image"
        assert cfg.label_col == "label"
        assert cfg.label_map == {}
        assert cfg.max_items is None
        assert cfg.token is False
        assert cfg.shuffle_buffer == 200

    def test_custom_values(self):
        from pykit_dataset.sources.huggingface import HuggingFaceSourceConfig

        cfg = HuggingFaceSourceConfig(
            repo="org/ds",
            split="test",
            image_col="img",
            label_col="cls",
            label_map={0: Label.REAL},
            max_items=50,
            token=True,
            shuffle_buffer=100,
        )
        assert cfg.split == "test"
        assert cfg.max_items == 50
        assert cfg.token is True


class TestHuggingFaceSource:
    def test_name(self):
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        cfg = HuggingFaceSourceConfig(repo="owner/dataset")
        source = HuggingFaceSource(cfg)
        assert source.name == "hf:owner/dataset"

    @pytest.mark.asyncio
    async def test_fetch_yields_items_with_pil_image(self):
        """When rows contain PIL Image objects, they should be converted to JPEG."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        rows = [
            {"image": pil_img, "label": 0},
            {"image": pil_img, "label": 1},
        ]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL, 1: Label.AI_GENERATED},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))
        mock_ds.shuffle = MagicMock(return_value=mock_ds)

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 2
        assert items[0].label == Label.REAL
        assert items[1].label == Label.AI_GENERATED
        assert items[0].media_type == MediaType.IMAGE
        assert items[0].extension == ".jpg"
        assert items[0].source_name == "hf:test/repo"
        assert items[0].metadata == {"repo": "test/repo", "split": "train"}

    @pytest.mark.asyncio
    async def test_fetch_yields_items_with_raw_bytes(self):
        """When rows contain raw bytes, PIL.Image.open is used."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        jpeg_bytes = _make_rgb_jpeg_bytes()
        rows = [{"image": jpeg_bytes, "label": 0}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL},
            max_items=5,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 1
        assert items[0].label == Label.REAL

    @pytest.mark.asyncio
    async def test_fetch_skips_missing_image(self):
        """Rows with no image column should be skipped."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        rows = [{"image": None, "label": 0}, {"not_image": b"data", "label": 0}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_skips_unmapped_label(self):
        """Rows with label not in label_map should be skipped."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        rows = [{"image": pil_img, "label": 99}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_with_all_label_map(self):
        """'all' key in label_map assigns the same label to every row."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        rows = [{"image": pil_img, "label": 0}, {"image": pil_img, "label": 1}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={"all": Label.AI_GENERATED},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 2
        assert all(i.label == Label.AI_GENERATED for i in items)

    @pytest.mark.asyncio
    async def test_fetch_per_class_balance(self):
        """With max_items and two labels, per-class balance is enforced."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        # 6 REAL then 6 AI — max_items=4 → 2 per class
        rows = [{"image": pil_img, "label": 0}] * 6 + [{"image": pil_img, "label": 1}] * 6

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL, 1: Label.AI_GENERATED},
            max_items=4,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 4
        real_count = sum(1 for i in items if i.label == Label.REAL)
        ai_count = sum(1 for i in items if i.label == Label.AI_GENERATED)
        assert real_count == 2
        assert ai_count == 2

    @pytest.mark.asyncio
    async def test_fetch_handles_load_failure(self):
        """If dataset loading fails, fetch yields nothing."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        cfg = HuggingFaceSourceConfig(repo="test/repo", label_map={0: Label.REAL})
        source = HuggingFaceSource(cfg)

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            side_effect=RuntimeError("network error"),
        ):
            items = [item async for item in source.fetch()]

        assert items == []

    @pytest.mark.asyncio
    async def test_fetch_skips_corrupt_image(self):
        """Rows with bad image data are skipped gracefully."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        rows = [{"image": b"not-a-valid-image", "label": 0}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_skips_missing_label_col(self):
        """Rows missing the label column are skipped."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        rows = [{"image": pil_img}]  # no 'label' key

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_map={0: Label.REAL},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_with_no_label_col(self):
        """When label_col is None and no 'all' in label_map, items are skipped."""
        from pykit_dataset.sources.huggingface import HuggingFaceSource, HuggingFaceSourceConfig

        pil_img = _make_pil_image()
        rows = [{"image": pil_img}]

        cfg = HuggingFaceSourceConfig(
            repo="test/repo",
            label_col=None,
            label_map={0: Label.REAL},
            max_items=10,
        )
        source = HuggingFaceSource(cfg)

        mock_ds = MagicMock()
        mock_ds.__iter__ = MagicMock(return_value=iter(rows))

        with patch(
            "pykit_dataset.sources.huggingface._load_and_shuffle",
            return_value=mock_ds,
        ):
            items = [item async for item in source.fetch()]

        assert len(items) == 0


class TestLoadAndShuffle:
    def test_load_and_shuffle(self):
        from pykit_dataset.sources.huggingface import _load_and_shuffle

        mock_ds = MagicMock()
        mock_shuffled = MagicMock()
        mock_ds.shuffle.return_value = mock_shuffled

        mock_datasets_mod = MagicMock()
        mock_datasets_mod.load_dataset = MagicMock(return_value=mock_ds)

        with patch.dict("sys.modules", {"datasets": mock_datasets_mod}):
            result = _load_and_shuffle("repo/name", "train", False, 200)

        mock_datasets_mod.load_dataset.assert_called_once_with(
            "repo/name", split="train", streaming=True, token=False
        )
        mock_ds.shuffle.assert_called_once_with(seed=42, buffer_size=200)
        assert result == mock_shuffled


class TestNextRow:
    def test_returns_next_item(self):
        from pykit_dataset.sources.huggingface import _next_row

        it = iter([1, 2, 3])
        assert _next_row(it) == 1
        assert _next_row(it) == 2

    def test_returns_none_on_exhaustion(self):
        from pykit_dataset.sources.huggingface import _next_row

        it = iter([])
        assert _next_row(it) is None


# ===========================================================================
# WebSource tests
# ===========================================================================


class TestWebSource:
    def test_name(self):
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL)
        assert source.name == "web:duckduckgo"

    def test_default_max_per_query(self):
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["q"], label=Label.REAL)
        assert source._max_per_query == 50

    @pytest.mark.asyncio
    async def test_fetch_yields_valid_images(self):
        """Successful image downloads should be yielded as DataItems."""
        from pykit_dataset.sources.web import WebSource

        jpeg_bytes = _make_rgb_jpeg_bytes(64, 64)  # larger to exceed 1000 byte threshold

        source = WebSource(queries=["test query"], label=Label.AI_GENERATED, max_per_query=2)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345&other"
        mock_search_resp.status_code = 200

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {
            "results": [
                {"image": "http://example.com/img1.jpg"},
                {"image": "http://example.com/img2.jpg"},
            ]
        }

        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.headers = {"content-type": "image/jpeg"}
        mock_img_resp.content = jpeg_bytes

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_img_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 2
        assert all(i.label == Label.AI_GENERATED for i in items)
        assert all(i.media_type == MediaType.IMAGE for i in items)
        assert items[0].metadata["query"] == "test query"

    @pytest.mark.asyncio
    async def test_fetch_skips_non_image_content(self):
        """Responses without image content-type are skipped."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL, max_per_query=5)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345&other"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"results": [{"image": "http://example.com/page.html"}]}

        mock_non_image_resp = MagicMock()
        mock_non_image_resp.status_code = 200
        mock_non_image_resp.headers = {"content-type": "text/html"}
        mock_non_image_resp.content = b"<html>not an image</html>"

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_non_image_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_skips_small_images(self):
        """Images smaller than 1000 bytes are skipped."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL, max_per_query=5)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"results": [{"image": "http://example.com/tiny.jpg"}]}

        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.headers = {"content-type": "image/jpeg"}
        mock_img_resp.content = b"tiny"  # < 1000 bytes

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_img_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_skips_failed_http(self):
        """Non-200 responses are skipped."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL, max_per_query=5)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"results": [{"image": "http://example.com/img.jpg"}]}

        mock_fail_resp = MagicMock()
        mock_fail_resp.status_code = 404

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_fail_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_fetch_deduplicates_urls(self):
        """Duplicate URLs across queries are deduplicated."""
        from pykit_dataset.sources.web import WebSource

        jpeg_bytes = _make_rgb_jpeg_bytes(64, 64)

        source = WebSource(queries=["q1", "q2"], label=Label.REAL, max_per_query=5)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        # Same URL in both query results
        mock_api_resp.json.return_value = {"results": [{"image": "http://example.com/same.jpg"}]}

        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.headers = {"content-type": "image/jpeg"}
        mock_img_resp.content = jpeg_bytes

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_img_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        # Same URL should only be fetched once
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_fetch_handles_search_failure(self):
        """If search raises, that query is skipped."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["failing query"], label=Label.REAL, max_per_query=5)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_search_no_vqd_returns_empty(self):
        """When vqd token is not found, _search returns empty list."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL)

        mock_resp = MagicMock()
        mock_resp.text = "no token here"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        result = await source._search(mock_client, "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_api_non_200_returns_empty(self):
        """When API returns non-200, _search returns empty list."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 500

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_search_resp
            return mock_api_resp

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)

        result = await source._search(mock_client, "test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_search_returns_image_urls(self):
        """Successful search returns list of image URLs."""
        from pykit_dataset.sources.web import WebSource

        source = WebSource(queries=["test"], label=Label.REAL)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=98765"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {
            "results": [
                {"image": "http://a.com/1.jpg"},
                {"image": "http://b.com/2.jpg"},
                {"other_key": "no image"},
            ]
        }

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_search_resp
            return mock_api_resp

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)

        result = await source._search(mock_client, "test query")
        assert result == ["http://a.com/1.jpg", "http://b.com/2.jpg"]

    @pytest.mark.asyncio
    async def test_fetch_png_extension(self):
        """PNG content-type should produce .png extension."""
        from pykit_dataset.sources.web import WebSource

        jpeg_bytes = _make_rgb_jpeg_bytes(64, 64)

        source = WebSource(queries=["test"], label=Label.REAL, max_per_query=1)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {"results": [{"image": "http://example.com/img.png"}]}

        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.headers = {"content-type": "image/png"}
        mock_img_resp.content = jpeg_bytes

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_img_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 1
        assert items[0].extension == ".png"

    @pytest.mark.asyncio
    async def test_fetch_respects_max_per_query(self):
        """Fetch stops after max_per_query images per query."""
        from pykit_dataset.sources.web import WebSource

        jpeg_bytes = _make_rgb_jpeg_bytes(64, 64)

        source = WebSource(queries=["test"], label=Label.REAL, max_per_query=1)

        mock_search_resp = MagicMock()
        mock_search_resp.text = "vqd=12345"

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = {
            "results": [
                {"image": "http://example.com/img1.jpg"},
                {"image": "http://example.com/img2.jpg"},
                {"image": "http://example.com/img3.jpg"},
            ]
        }

        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.headers = {"content-type": "image/jpeg"}
        mock_img_resp.content = jpeg_bytes

        mock_client = AsyncMock()

        async def mock_get(url, **kwargs):
            if "duckduckgo.com" in url and "i.js" not in url:
                return mock_search_resp
            elif "i.js" in url:
                return mock_api_resp
            else:
                return mock_img_resp

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("pykit_dataset.sources.web.httpx.AsyncClient", return_value=mock_client):
            items = [item async for item in source.fetch()]

        assert len(items) == 1
