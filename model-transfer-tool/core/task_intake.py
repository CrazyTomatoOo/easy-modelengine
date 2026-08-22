"""Task intake —— 任务进入系统的唯一接口:把 TaskDraft 变成 TaskConfig。

ADR-0001:校验、本地目录扫描、源文件列表、TaskFile 组装全部收进本模块;
GUI 只发射原始选择快照 TaskDraft,不再构造下载器、不再映射任务类型字符串。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from core.downloaders.hf_downloader import HuggingFaceDownloader
from core.downloaders.local_strategy import LocalDirStrategy
from core.downloaders.ms_downloader import ModelScopeDownloader
from core.interfaces import DownloadStrategy
from core.task_config import TaskConfig, TaskFile, TaskType


class DraftValidationError(ValueError):
    """TaskDraft 校验失败——输入不合法,未创建任务。"""


@dataclass
class TaskDraft:
    """向导各步骤的原始选择快照,不做业务解释(CONTEXT.md:TaskDraft)。"""

    source: str  # huggingface | modelscope | local
    model_id: str  # 远程模型 ID;本地模式下为本地目录路径
    revision: str
    task_type_name: str  # 向导任务类型 radio 的值(download_only | download_transfer | transfer_local)
    cache_dir: Optional[str] = None
    file_filter: Optional[str] = None
    server: Optional[str] = None
    target_dir: Optional[str] = None


_TASK_TYPE_MAP: dict[str, TaskType] = {
    "download_only": TaskType.DOWNLOAD_ONLY,
    "download_transfer": TaskType.FULL_PIPELINE,
    "transfer_local": TaskType.TRANSFER_ONLY,
}

_DEFAULT_STRATEGIES: Mapping[str, DownloadStrategy] = {
    "huggingface": HuggingFaceDownloader(),
    "modelscope": ModelScopeDownloader(),
    "local": LocalDirStrategy(),
}


def resolve_strategy(
    source: str,
    strategies: Optional[Mapping[str, DownloadStrategy]] = None,
) -> DownloadStrategy:
    """返回指定来源的下载策略;未知来源抛 DraftValidationError。"""
    table = strategies if strategies is not None else _DEFAULT_STRATEGIES
    try:
        return table[source]
    except KeyError:
        raise DraftValidationError(f"不支持的模型来源: {source}") from None


def _build_task_type(task_type_name: str) -> TaskType:
    try:
        return _TASK_TYPE_MAP[task_type_name]
    except KeyError:
        raise DraftValidationError(f"未知任务类型: {task_type_name}") from None


def validate(
    draft: TaskDraft,
    strategies: Optional[Mapping[str, DownloadStrategy]] = None,
) -> None:
    """校验 TaskDraft;不合法抛 DraftValidationError。可被向导在提交前同步调用。"""
    task_type = _build_task_type(draft.task_type_name)

    if draft.source == "local":
        if not draft.model_id:
            raise DraftValidationError("本地模型目录为空")
        if not Path(draft.model_id).is_dir():
            raise DraftValidationError(f"本地模型目录不存在: {draft.model_id}")
        if task_type != TaskType.TRANSFER_ONLY:
            raise DraftValidationError("本地模型来源仅支持『仅传输本地已有文件』任务")
    else:
        if not draft.model_id:
            raise DraftValidationError("模型 ID 为空")
        resolve_strategy(draft.source, strategies)


def build(
    draft: TaskDraft,
    strategies: Optional[Mapping[str, DownloadStrategy]] = None,
) -> TaskConfig:
    """把向导发射的 TaskDraft 变成可执行的 TaskConfig。

    校验失败抛 DraftValidationError;文件列表失败向上传播(不创建任务)。
    """
    task_type = _build_task_type(draft.task_type_name)
    validate(draft, strategies)

    if task_type == TaskType.TRANSFER_ONLY and draft.source != "local":
        task_files = []
    else:
        strategy = resolve_strategy(draft.source, strategies)
        files = strategy.list_files(draft.model_id, draft.revision)
        task_files = [TaskFile(file_path=f.path, file_size=f.size) for f in files]

    return TaskConfig(
        task_type=task_type,
        model_source=draft.source,
        model_id=draft.model_id,
        revision=draft.revision,
        local_cache_dir=Path(draft.cache_dir) if draft.cache_dir else Path("cache"),
        file_filter=draft.file_filter or None,
        remote_host=draft.server,
        remote_path=draft.target_dir,
        files=task_files,
    )