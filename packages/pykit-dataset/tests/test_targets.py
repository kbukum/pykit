"""Tests for HuggingFace and Kaggle targets with mocked external dependencies."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pykit_dataset.target import PublishResult

# ===========================================================================
# HuggingFaceTarget tests
# ===========================================================================


class TestHuggingFaceTarget:
    def test_name(self):
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        target = HuggingFaceTarget(repo_id="user/my-dataset")
        assert target.name == "huggingface:user/my-dataset"

    def test_default_config(self):
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        target = HuggingFaceTarget(repo_id="user/ds")
        assert target._repo_id == "user/ds"
        assert target._private is True
        assert target._batch_size == 10
        assert target._batch_delay == 2.0

    def test_custom_config(self):
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        target = HuggingFaceTarget(repo_id="org/ds", private=False, batch_size=5, batch_delay=1.0)
        assert target._private is False
        assert target._batch_size == 5
        assert target._batch_delay == 1.0

    @pytest.mark.asyncio
    async def test_publish_single_batch(self, tmp_path):
        """Publish with files fitting in a single batch."""
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        # Create test files
        (tmp_path / "real").mkdir()
        (tmp_path / "real" / "img1.jpg").write_bytes(b"image1")
        (tmp_path / "real" / "img2.jpg").write_bytes(b"image2")

        target = HuggingFaceTarget(repo_id="user/test-ds", batch_size=10)

        mock_api = MagicMock()
        mock_commit_op = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "huggingface_hub": MagicMock(
                        HfApi=MagicMock(return_value=mock_api),
                        CommitOperationAdd=mock_commit_op,
                    ),
                },
            ),
        ):
            result = await target.publish(tmp_path)

        assert isinstance(result, PublishResult)
        assert result.target_name == "huggingface:user/test-ds"
        assert result.files_published == 2
        assert "user/test-ds" in result.location
        mock_api.create_repo.assert_called_once_with(
            repo_id="user/test-ds",
            repo_type="dataset",
            private=True,
            exist_ok=True,
        )
        mock_api.create_commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_multiple_batches(self, tmp_path):
        """Publish with files spanning multiple batches."""
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        # Create 5 files, batch_size=2 → 3 batches
        for i in range(5):
            (tmp_path / f"file{i}.txt").write_bytes(f"content{i}".encode())

        target = HuggingFaceTarget(repo_id="user/multi-batch", batch_size=2, batch_delay=0.0)

        mock_api = MagicMock()
        mock_commit_op = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "huggingface_hub": MagicMock(
                        HfApi=MagicMock(return_value=mock_api),
                        CommitOperationAdd=mock_commit_op,
                    ),
                },
            ),
        ):
            result = await target.publish(tmp_path)

        assert result.files_published == 5
        assert mock_api.create_commit.call_count == 3

    @pytest.mark.asyncio
    async def test_publish_empty_directory(self, tmp_path):
        """Publishing an empty directory should upload 0 files."""
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        target = HuggingFaceTarget(repo_id="user/empty-ds")

        mock_api = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "huggingface_hub": MagicMock(
                    HfApi=MagicMock(return_value=mock_api),
                    CommitOperationAdd=MagicMock(),
                ),
            },
        ):
            result = await target.publish(tmp_path)

        assert result.files_published == 0
        mock_api.create_commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_result_message(self, tmp_path):
        """Result message includes the HF URL."""
        from pykit_dataset.targets.huggingface import HuggingFaceTarget

        (tmp_path / "test.txt").write_bytes(b"data")
        target = HuggingFaceTarget(repo_id="org/dataset-v2")

        mock_api = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "huggingface_hub": MagicMock(
                    HfApi=MagicMock(return_value=mock_api),
                    CommitOperationAdd=MagicMock(),
                ),
            },
        ):
            result = await target.publish(tmp_path)

        assert result.location == "https://huggingface.co/datasets/org/dataset-v2"
        assert "org/dataset-v2" in result.message


# ===========================================================================
# KaggleTarget tests
# ===========================================================================


class TestKaggleTarget:
    def test_name(self):
        from pykit_dataset.targets.kaggle import KaggleTarget

        target = KaggleTarget(handle="user/my-kaggle-ds")
        assert target.name == "kaggle:user/my-kaggle-ds"

    def test_default_config(self):
        from pykit_dataset.targets.kaggle import KaggleTarget

        target = KaggleTarget(handle="user/ds")
        assert target._handle == "user/ds"
        assert target._version_notes == ""
        assert target._ignore_patterns == []

    def test_custom_config(self):
        from pykit_dataset.targets.kaggle import KaggleTarget

        target = KaggleTarget(
            handle="user/ds",
            version_notes="v2 release",
            ignore_patterns=["*.tmp", ".git"],
        )
        assert target._version_notes == "v2 release"
        assert target._ignore_patterns == ["*.tmp", ".git"]

    @pytest.mark.asyncio
    async def test_publish_basic(self, tmp_path):
        """Basic publish uploads files to Kaggle."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        (tmp_path / "data.csv").write_bytes(b"col1,col2\n1,2")
        (tmp_path / "meta.json").write_bytes(b'{"key": "val"}')

        target = KaggleTarget(handle="user/test-dataset")

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            result = await target.publish(tmp_path)

        assert isinstance(result, PublishResult)
        assert result.target_name == "kaggle:user/test-dataset"
        assert result.files_published == 2
        assert "kaggle.com" in result.location
        mock_kagglehub.dataset_upload.assert_called_once_with(
            handle="user/test-dataset",
            local_dataset_dir=str(tmp_path),
        )

    @pytest.mark.asyncio
    async def test_publish_with_version_notes(self, tmp_path):
        """Version notes are passed to kagglehub."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        (tmp_path / "file.txt").write_bytes(b"data")

        target = KaggleTarget(handle="user/ds", version_notes="Initial release")

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            await target.publish(tmp_path)

        mock_kagglehub.dataset_upload.assert_called_once_with(
            handle="user/ds",
            local_dataset_dir=str(tmp_path),
            version_notes="Initial release",
        )

    @pytest.mark.asyncio
    async def test_publish_with_ignore_patterns(self, tmp_path):
        """Ignore patterns are passed to kagglehub."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        (tmp_path / "file.txt").write_bytes(b"data")

        target = KaggleTarget(handle="user/ds", ignore_patterns=["*.log"])

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            await target.publish(tmp_path)

        mock_kagglehub.dataset_upload.assert_called_once_with(
            handle="user/ds",
            local_dataset_dir=str(tmp_path),
            ignore_patterns=["*.log"],
        )

    @pytest.mark.asyncio
    async def test_publish_empty_directory(self, tmp_path):
        """Publishing an empty directory reports 0 files."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        target = KaggleTarget(handle="user/empty-ds")

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            result = await target.publish(tmp_path)

        assert result.files_published == 0

    @pytest.mark.asyncio
    async def test_publish_result_location(self, tmp_path):
        """Result location is a valid Kaggle URL."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        (tmp_path / "file.txt").write_bytes(b"data")
        target = KaggleTarget(handle="org/my-dataset")

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            result = await target.publish(tmp_path)

        assert result.location == "https://www.kaggle.com/datasets/org/my-dataset"
        assert "org/my-dataset" in result.message

    @pytest.mark.asyncio
    async def test_publish_nested_files(self, tmp_path):
        """Nested directory structure is counted correctly."""
        from pykit_dataset.targets.kaggle import KaggleTarget

        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "nested.txt").write_bytes(b"nested")
        (tmp_path / "top.txt").write_bytes(b"top")

        target = KaggleTarget(handle="user/nested-ds")

        mock_kagglehub = MagicMock()

        with patch.dict("sys.modules", {"kagglehub": mock_kagglehub}):
            result = await target.publish(tmp_path)

        assert result.files_published == 2
