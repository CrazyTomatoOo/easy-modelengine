from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path


class TaskType(Enum):
    DOWNLOAD_ONLY = "download_only"
    TRANSFER_ONLY = "transfer_only"
    FULL_PIPELINE = "full_pipeline"


class TaskState(Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    PAUSED_DOWNLOAD = "paused_dl"
    VERIFYING = "verifying"
    TRANSFERRING = "transferring"
    PAUSED_TRANSFER = "paused_tx"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageState(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskFile:
    file_path: str
    file_size: int
    expected_hash: Optional[str] = None
    hash_algorithm: Optional[str] = None
    download_state: StageState = StageState.NOT_STARTED
    download_bytes: int = 0
    local_path: Optional[Path] = None
    verify_state: StageState = StageState.NOT_STARTED
    actual_hash: Optional[str] = None
    transfer_state: StageState = StageState.NOT_STARTED
    transfer_bytes: int = 0
    remote_path: Optional[str] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class TaskConfig:
    task_type: TaskType
    model_source: str
    model_id: str
    revision: str = "main"
    local_cache_dir: Path = field(default_factory=lambda: Path("cache"))
    file_filter: Optional[str] = None
    remote_host: Optional[str] = None
    remote_path: Optional[str] = None
    files: list[TaskFile] = field(default_factory=list)
