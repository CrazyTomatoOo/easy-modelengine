"""Task intake 接口测试——spec 定义的唯一测试面:build(draft, strategies) -> TaskConfig。"""

from pathlib import Path

import pytest

from core.task_intake import TaskDraft, build, validate, resolve_strategy, DraftValidationError
from core.task_config import TaskConfig, TaskType, TaskFile
from core.interfaces import FileInfo, DownloadStrategy
from core.downloaders.local_strategy import LocalDirStrategy


class FakeStrategy(DownloadStrategy):
    """远程来源的测试替身:记录 list 调用,不触碰网络。"""

    def __init__(self, files=None):
        self.files = files if files is not None else [FileInfo(path="model.bin", size=1024)]
        self.list_calls = []

    def list_files(self, model_id, revision):
        self.list_calls.append((model_id, revision))
        return self.files
    def download_file(self, model_id, revision, file_info, local_path, progress_callback=None):
        return True


STRATEGIES = {
    "huggingface": FakeStrategy(),
    "modelscope": FakeStrategy(),
    "local": LocalDirStrategy(),
}


def _draft(**overrides):
    base = dict(
        source="huggingface",
        model_id="bert-base-uncased",
        revision="main",
        task_type_name="download_only",
    )
    base.update(overrides)
    return TaskDraft(**base)


class TestBuildRemote:
    def test_expected_hash_carried_from_listing(self):
        strategies = {"huggingface": FakeStrategy([FileInfo(path="big.bin", size=10, expected_hash="a" * 64)])}
        config = build(_draft(), strategies=strategies)
        assert config.files[0].expected_hash == "a" * 64
        assert config.files[0].hash_algorithm == "sha256"

    def test_no_hash_stays_none(self):
        config = build(_draft(), strategies=STRATEGIES)
        assert config.files[0].expected_hash is None
        assert config.files[0].hash_algorithm is None

    def test_download_only_maps_task_type(self):
        config = build(_draft(), strategies=STRATEGIES)
        assert config.task_type == TaskType.DOWNLOAD_ONLY

    def test_full_pipeline_lists_files_and_copies_fields(self):
        strategies = {"huggingface": FakeStrategy([FileInfo(path="a.bin", size=10), FileInfo(path="b.bin", size=20)])}
        draft = _draft(
            model_id="org/model",
            revision="v1.0",
            task_type_name="download_transfer",
            cache_dir="/tmp/cache",
            file_filter="*.bin",
            server="srv-1",
            target_dir="/models",
        )
        config = build(draft, strategies=strategies)

        assert config.task_type == TaskType.FULL_PIPELINE
        assert config.model_source == "huggingface"
        assert config.model_id == "org/model"
        assert config.revision == "v1.0"
        assert config.local_cache_dir == Path("/tmp/cache")
        assert config.file_filter == "*.bin"
        assert config.remote_host == "srv-1"
        assert config.remote_path == "/models"
        assert [f.file_path for f in config.files] == ["a.bin", "b.bin"]
        assert [f.file_size for f in config.files] == [10, 20]
        assert strategies["huggingface"].list_calls == [("org/model", "v1.0")]

    def test_transfer_only_remote_source_rejected(self):
        """远程源 + 仅传输本地文件 = 0 文件任务秒完成(用户可跳过下载)——必须拒绝。"""
        draft = _draft(source="modelscope", task_type_name="transfer_local")
        with pytest.raises(DraftValidationError, match="本地模型来源"):
            validate(draft, strategies=STRATEGIES)

    def test_build_rejects_empty_repo(self):
        """仓库无文件 → 拒绝创建(空列表任务秒 completed 且进度 0%)。"""
        strategies = {"huggingface": FakeStrategy([])}
        with pytest.raises(DraftValidationError, match="没有可"):
            build(_draft(), strategies=strategies)

    def test_build_rejects_empty_local_dir(self):
        """本地空目录传输同样无意义,拒绝。"""
        import tempfile

        empty = tempfile.mkdtemp()
        draft = _draft(source="local", model_id=empty, revision="local", task_type_name="transfer_local")
        with pytest.raises(DraftValidationError, match="没有可"):
            build(draft, strategies=STRATEGIES)

    def test_default_cache_dir(self):
        config = build(_draft(), strategies=STRATEGIES)
        assert config.local_cache_dir == Path("cache")

    def test_empty_model_id_raises(self):
        with pytest.raises(DraftValidationError):
            build(_draft(model_id=""), strategies=STRATEGIES)

    def test_unknown_task_type_raises(self):
        with pytest.raises(DraftValidationError):
            build(_draft(task_type_name="bogus"), strategies=STRATEGIES)

    def test_unknown_source_raises(self):
        with pytest.raises(DraftValidationError):
            build(_draft(source="s3"), strategies=STRATEGIES)


class TestBuildLocal:
    def test_local_mode_lists_files_through_strategy(self, tmp_path):
        (tmp_path / "model.bin").write_bytes(b"x" * 100)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "cfg.json").write_text("{}")

        draft = _draft(source="local", model_id=str(tmp_path), revision="local", task_type_name="transfer_local")
        config = build(draft, strategies=STRATEGIES)

        by_path = {f.file_path: f.file_size for f in config.files}
        assert by_path == {"model.bin": 100, "sub/cfg.json": 2}

    def test_local_injected_strategy_is_used(self, tmp_path):
        strategy = FakeStrategy([FileInfo(path="custom.bin", size=5)])
        strategies = {"local": strategy}

        draft = _draft(source="local", model_id=str(tmp_path), revision="local", task_type_name="transfer_local")
        config = build(draft, strategies=strategies)

        assert [f.file_path for f in config.files] == ["custom.bin"]
        assert strategy.list_calls == [(str(tmp_path), "local")]

    def test_local_missing_dir_raises(self):
        with pytest.raises(DraftValidationError):
            build(_draft(source="local", model_id="/nonexistent-dir-xyz"), strategies=STRATEGIES)

    def test_local_empty_path_raises(self):
        with pytest.raises(DraftValidationError):
            build(_draft(source="local", model_id=""), strategies=STRATEGIES)

    def test_local_source_rejects_download_types(self, tmp_path):
        draft = _draft(source="local", model_id=str(tmp_path), task_type_name="download_only")
        with pytest.raises(DraftValidationError):
            build(draft, strategies=STRATEGIES)


class TestValidate:
    def test_validate_passes_for_valid_remote(self):
        validate(_draft(), strategies=STRATEGIES)

    def test_validate_rejects_missing_local_dir(self):
        draft = _draft(source="local", model_id="/nonexistent-dir-xyz", task_type_name="transfer_local")
        with pytest.raises(DraftValidationError):
            validate(draft, strategies=STRATEGIES)

    def test_validate_rejects_unknown_source(self):
        with pytest.raises(DraftValidationError):
            validate(_draft(source="s3"), strategies=STRATEGIES)


class TestTaskTypeMapping:
    def test_maps_all_three_types(self, tmp_path):
        mapping = {
            "download_only": TaskType.DOWNLOAD_ONLY,
            "download_transfer": TaskType.FULL_PIPELINE,
            "transfer_local": TaskType.TRANSFER_ONLY,
        }
        for name, expected in mapping.items():
            draft = _draft(task_type_name=name)
            if expected == TaskType.TRANSFER_ONLY:
                # 仅传输只对本地源合法(新校验);用临时目录承载映射断言
                (tmp_path / "m.bin").write_bytes(b"x")
                draft = _draft(
                    source="local", model_id=str(tmp_path), revision="local",
                    task_type_name=name,
                )
            config = build(draft, strategies=STRATEGIES)
            assert config.task_type == expected


class TestLocalDirStrategy:
    def test_list_files_scans_rel_paths(self, tmp_path):
        (tmp_path / "model.bin").write_bytes(b"x" * 7)
        (tmp_path / "nested").mkdir()
        (tmp_path / "nested" / "cfg.json").write_text("{}")

        files = LocalDirStrategy().list_files(str(tmp_path), "local")

        assert {f.path for f in files} == {"model.bin", "nested/cfg.json"}
        assert {f.size for f in files} == {7, 2}

    def test_download_copies_file(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "model.bin").write_bytes(b"data")
        dest = tmp_path / "dest" / "model.bin"
        dest.parent.mkdir()

        strategy = LocalDirStrategy()
        file_info = FileInfo(path="model.bin", size=4)
        progress = []
        result = strategy.download_file(str(src), "local", file_info, dest, progress_callback=lambda c, t: progress.append((c, t)))

        assert result is True
        assert dest.read_bytes() == b"data"
        assert progress == [(4, 4)]

    def test_download_missing_source_returns_false(self, tmp_path):
        strategy = LocalDirStrategy()
        file_info = FileInfo(path="missing.bin", size=4)
        result = strategy.download_file(str(tmp_path), "local", file_info, tmp_path / "out.bin")
        assert result is False


class TestResolveStrategy:
    def test_default_mapping_covers_three_sources(self):
        for source in ("huggingface", "modelscope", "local"):
            strategy = resolve_strategy(source)
            assert isinstance(strategy, DownloadStrategy)

    def test_unknown_source_raises(self):
        with pytest.raises(DraftValidationError):
            resolve_strategy("s3")

    def test_injected_mapping_wins(self):
        strategy = FakeStrategy()
        assert resolve_strategy("custom", strategies={"custom": strategy}) is strategy


# 来源 × 任务类型 合法矩阵:正式回归,防止再漏一格(远程+仅传输、本地+下载都是洞)
_SOURCE_TYPES = [
    ("huggingface", "download_only", True),
    ("huggingface", "download_transfer", True),
    ("huggingface", "transfer_local", False),
    ("modelscope", "download_only", True),
    ("modelscope", "download_transfer", True),
    ("modelscope", "transfer_local", False),
    ("local", "download_only", False),
    ("local", "download_transfer", False),
    ("local", "transfer_local", True),
]


class TestIntakeMatrix:
    @pytest.mark.parametrize("source,task_type,legit", _SOURCE_TYPES)
    def test_validate_matrix(self, tmp_path, source, task_type, legit):
        (tmp_path / "m.bin").write_bytes(b"x")
        draft = _draft(source=source, task_type_name=task_type)
        if source == "local":
            draft = _draft(
                source="local", model_id=str(tmp_path), revision="local",
                task_type_name=task_type,
            )
        if legit:
            validate(draft, strategies=STRATEGIES)  # 合法组合必须放行
        else:
            with pytest.raises(DraftValidationError):
                validate(draft, strategies=STRATEGIES)