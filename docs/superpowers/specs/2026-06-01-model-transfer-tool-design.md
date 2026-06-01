# 模型下载与远程传输工具 — 设计文档

**日期**: 2026-06-01
**版本**: v1.0
**状态**: 待评审

---

## 1. 项目概述

### 1.1 产品定位

开发一款面向 Windows 平台的桌面 GUI 工具，用于从公网模型仓库（HuggingFace、ModelScope）下载模型权重文件到本地，并通过 rsync 协议传输到远程服务器的指定目录。支持多文件并行下载/传输、断点续传、完整性校验、任务队列管理。

### 1.2 核心目标

- **降低模型部署门槛**：让非技术用户也能轻松将模型从云端下载并传输到内网/私有服务器
- **保障传输可靠性**：断点续传 + 完整性校验，确保大文件（GB 级）传输不中断、不损坏
- **提升传输效率**：多文件并行下载/传输，最大化带宽利用率
- **隐私安全**：密码/SSH key 加密存储，不泄露敏感信息
- **绿色便携**：解压即用，无需安装，不污染系统环境

### 1.3 目标用户

- AI 模型部署工程师
- 运维人员
- 需要将模型从公网同步到私有服务器的研究人员

---

## 2. 需求规格

### 2.1 功能需求

#### FR-001: 模型源支持
- 支持 **HuggingFace** 模型仓库下载
- 支持 **ModelScope** 模型仓库下载
- 支持选择模型版本（branch / tag / commit）
- 支持配置 HuggingFace Access Token（用于下载受限/Gated 模型）
- 支持配置 ModelScope 登录凭据
- Token 和凭据使用与服务器密码相同的加密存储机制（AES-256-GCM）
- 遇到 403 (Gated Repository) 时，提示用户配置相应平台的 Access Token
- Token 配置支持"记住"选项（加密存储），或每次临时输入

#### FR-002: 下载功能
- 支持将模型文件下载到本地缓存目录
- 支持 **断点续传**（下载中断后，下次从断点继续）
- 支持 **多文件并行下载**（可配置并发数，默认 4）
- 支持 **代理/加速镜像配置**（可选，不强制依赖）

#### FR-003: 完整性校验
- 下载完成后 **自动校验** 文件完整性（SHA256/MD5）
- 校验失败自动重新下载（最多重试 2 次）
- 校验通过后进入下一阶段

#### FR-004: 远程传输
- 支持通过 **rsync** 协议传输到远程服务器
- 支持 **断点续传**（传输中断后，下次从断点继续）
- 支持 **多文件并行传输**（可配置并发数，默认 2）
- 传输完成后支持远程校验

#### FR-005: 任务队列管理
- 支持创建 **多任务队列**
- 支持三种任务类型：
  - `DOWNLOAD_ONLY`: 仅下载到本地
  - `TRANSFER_ONLY`: 仅传输本地已有文件
  - `FULL_PIPELINE`: 下载 + 传输完整流程
- 支持任务的 **暂停/恢复/取消**
- 支持失败任务的 **单独重试**（仅重试失败的文件，不重复已成功文件）

#### FR-006: 远程服务器管理
- 支持配置多台远程服务器（保存为模板）
- 支持两种认证方式：**密码认证** 和 **SSH Key 认证**
- 支持测试连接（配置时验证连通性）

#### FR-007: GUI 界面
- **向导式操作流程**（4 步：选择模型 → 配置参数 → 确认执行 → 执行监控）
- **任务队列侧边栏**（实时展示多任务状态）
- **日志/状态面板**（实时输出操作日志）
- **专业详情面板**（文件树预览、进度详情）

#### FR-008: 绿色便携
- **免安装**，解压即用
- 所有数据（配置、数据库、缓存、日志）存储在应用目录内
- 支持从 U 盘/移动硬盘运行

### 2.2 非功能需求

#### NFR-001: 性能
- 下载速度：充分利用可用带宽（多文件并行）
- 传输速度：rsync 增量传输，仅传输变更部分
- UI 响应：所有 I/O 操作在后台线程执行，UI 不卡顿

#### NFR-002: 可靠性
- 断网/断电恢复：重启应用后可恢复未完成的任务
- 错误重试：自动重试机制（指数退避）
- 数据一致性：校验失败自动重试，确保端到端一致性

#### NFR-003: 安全性
- 凭据加密：密码/SSH key 使用 AES-256-GCM 加密存储
- 主密钥保护：加密主密钥存储在系统钥匙串（Windows Credential）
- 配置文件不存明文敏感信息

#### NFR-004: 可扩展性
- 下载策略接口化：支持未来扩展其他模型源（CivitAI 等）
- 传输策略接口化：支持未来扩展其他传输协议（SCP、S3 等）
- 配置化并发度：用户可调整各阶段并行度

#### NFR-005: 兼容性
- **目标平台**: Windows 10/11（64位）
- **依赖要求**: 用户需自行安装 rsync（如 Git for Windows 自带，或 Cygwin/MSYS2）
- **Python 版本**: 3.10+

---

## 3. 系统架构

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        GUI 层 (PyQt6)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  向导面板    │  │  任务队列    │  │  日志/状态面板   │  │
│  │  (引导流程)  │  │  (多任务管理)│  │  (实时监控)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      调度控制层 (主线程)                      │
│         任务队列管理器  ←  状态机  →  配置管理器             │
├─────────────────────────────────────────────────────────────┤
│                     工作线程池 (QThreadPool)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ 下载工作线程 │  │ 校验工作线程 │  │ 传输工作线程     │  │
│  │ (并行 N 个)  │  │ (并行 M 个)  │  │ (并行 K 个)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      数据持久化层                            │
│         SQLite (任务记录、配置、缓存索引、日志)               │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 架构设计原则

1. **主线程隔离**: 主线程只处理 UI 渲染和任务调度，所有 I/O 操作（下载、传输、校验）在工作线程执行
2. **阶段串行、内部并行**: 下载 → 校验 → 传输 三阶段串行执行，但每阶段内部多文件并行处理
3. **状态机驱动**: 每个任务经历明确的状态流转，`pending → downloading → verifying → transferring → completed/failed`
4. **线程安全通信**: 工作线程通过 Qt 信号槽（Signal/Slot）与主线程通信，避免直接操作 UI
5. **持久化优先**: 关键状态变更立即写入 SQLite，确保崩溃后可恢复

### 3.3 模块划分

| 模块 | 文件路径 | 职责 |
|------|----------|------|
| `MainWindow` | `gui/main_window.py` | 主窗口、布局管理、面板切换 |
| `WizardPanel` | `gui/wizard_panel.py` | 向导式操作流程（4步引导） |
| `TaskPanel` | `gui/task_panel.py` | 任务队列展示、状态监控、操作按钮 |
| `LogPanel` | `gui/log_panel.py` | 实时日志输出、过滤、导出 |
| `TaskManager` | `core/task_manager.py` | 任务生命周期管理、状态机、队列调度 |
| `TaskConfig` | `core/task_config.py` | 任务配置数据模型 |
| `DownloadStrategy` | `core/interfaces.py` | 下载策略抽象接口 |
| `HuggingFaceDownloader` | `core/downloaders/hf_downloader.py` | HuggingFace 下载实现 |
| `ModelScopeDownloader` | `core/downloaders/ms_downloader.py` | ModelScope 下载实现 |
| `TransferStrategy` | `core/interfaces.py` | 传输策略抽象接口 |
| `RsyncTransfer` | `core/transfers/rsync_transfer.py` | rsync 传输实现 |
| `FileVerifier` | `core/verifier.py` | SHA256/MD5 文件校验 |
| `ConfigManager` | `core/config.py` | 应用配置、代理设置、服务器配置管理 |
| `Database` | `core/database.py` | SQLite 数据访问层（DAO） |
| `SecureStorage` | `utils/crypto.py` | 密码/SSH key 加密存储 |
| `Logger` | `utils/logger.py` | 结构化日志（文件 + GUI 输出） |

---

## 4. 核心设计

### 4.1 任务状态机

```python
class TaskState(Enum):
    PENDING = "pending"                   # 等待执行
    DOWNLOADING = "downloading"           # 正在下载
    PAUSED_DOWNLOAD = "paused_dl"         # 下载暂停（断点续传）
    VERIFYING = "verifying"               # 正在校验
    TRANSFERRING = "transferring"         # 正在传输
    PAUSED_TRANSFER = "paused_tx"         # 传输暂停（断点续传）
    COMPLETED = "completed"               # 全部完成
    FAILED = "failed"                     # 失败（可重试）
    CANCELLED = "cancelled"               # 用户取消
```

**状态流转规则**:

```
                    ┌──────────────────────────────┐
                    │                              │
                    ▼                              │
[PENDING] ──→ [DOWNLOADING] ──→ [VERIFYING] ──→ [TRANSFERRING] ──→ [COMPLETED]
    │              │    │              │              │                  │
    │              │    ▼              │              │                  │
    │              │ [PAUSED_DOWNLOAD] │              │                  │
    │              │    │              │              │                  │
    │              ▼    ▼              ▼              ▼                  ▼
    │          [FAILED] / [CANCELLED]─────────────────────────────────────┘
    │
    └── (TRANSFER_ONLY 类型跳过下载和校验，直接进入 TRANSFERRING)
    └── (DOWNLOAD_ONLY 类型传输阶段标记为 SKIPPED)
```

### 4.2 阶段状态独立持久化

每个阶段独立记录状态，支持阶段解耦：

```python
class StageState(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TaskFile:
    """任务文件级别的状态跟踪"""
    file_path: str           # 相对路径，如 "pytorch_model.bin"
    file_size: int           # 文件大小（字节）
    expected_hash: str       # 期望的 SHA256/MD5 值
    hash_algorithm: str      # "sha256" | "md5"
    
    # 下载阶段
    download_state: StageState
    download_bytes: int      # 已下载字节（断点续传进度）
    local_path: Path         # 本地绝对路径
    
    # 校验阶段
    verify_state: StageState
    actual_hash: str         # 实际计算出的 hash
    
    # 传输阶段
    transfer_state: StageState
    transfer_bytes: int      # 已传输字节（断点续传进度）
    remote_path: str         # 远程目标路径
    
    # 错误处理
    retry_count: int         # 失败重试次数（默认 0，最大 3）
    error_message: str       # 最后一次错误信息
```

### 4.3 下载/传输抽象接口（策略模式）

#### DownloadStrategy 接口

```python
class DownloadStrategy(ABC):
    """下载策略抽象基类"""
    
    @abstractmethod
    def list_files(self, model_id: str, revision: str) -> list[FileInfo]:
        """列出模型文件清单（含路径和大小）"""
        pass
    
    @abstractmethod
    def download_file(self, model_id: str, revision: str,
                     file_info: FileInfo, local_path: Path,
                     progress_callback: Callable[[int, int], None]) -> bool:
        """下载单个文件，支持断点续传
        
        Args:
            progress_callback: 进度回调 (已下载字节, 总字节)
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def get_checksum(self, model_id: str, revision: str,
                    file_path: str) -> Optional[tuple[str, str]]:
        """获取远程校验值
        
        Returns:
            (hash_algorithm, hash_value) 或 None（不支持校验）
        """
        pass
```

#### TransferStrategy 接口

```python
class TransferStrategy(ABC):
    """传输策略抽象基类"""
    
    @abstractmethod
    def transfer_file(self, local_path: Path, remote_path: str,
                     progress_callback: Callable[[int, int], None]) -> bool:
        """传输单个文件，支持断点续传"""
        pass
    
    @abstractmethod
    def verify_remote_checksum(self, remote_path: str,
                              expected_hash: str, algorithm: str) -> bool:
        """校验远程文件完整性"""
        pass
    
    @abstractmethod
    def check_connectivity(self) -> tuple[bool, str]:
        """检查连接性
        
        Returns:
            (是否可用, 错误信息)
        """
        pass
```

### 4.4 多阶段并行调度

```python
class TaskManager:
    """任务队列管理器"""
    
    def __init__(self):
        self.download_pool = QThreadPool()
        self.download_pool.setMaxThreadCount(self.config.download_concurrency)
        
        self.verify_pool = QThreadPool()
        self.verify_pool.setMaxThreadCount(self.config.verify_concurrency)
        
        self.transfer_pool = QThreadPool()
        self.transfer_pool.setMaxThreadCount(self.config.transfer_concurrency)
    
    def execute_task(self, task: Task):
        """执行任务"""
        if task.task_type in (TaskType.DOWNLOAD_ONLY, TaskType.FULL_PIPELINE):
            self._execute_download_stage(task)
        elif task.task_type == TaskType.TRANSFER_ONLY:
            self._execute_transfer_stage(task)
    
    def _execute_download_stage(self, task: Task):
        """执行下载阶段"""
        task.state = TaskState.DOWNLOADING
        self.db.update_task(task)
        
        # 为每个待下载的文件创建工作线程
        pending_files = [f for f in task.files if f.download_state == StageState.NOT_STARTED]
        for file_info in pending_files:
            worker = DownloadWorker(task, file_info)
            worker.signals.progress.connect(self._on_download_progress)
            worker.signals.finished.connect(self._on_download_file_finished)
            self.download_pool.start(worker)
    
    def _on_download_file_finished(self, task_id: str, file_path: str, success: bool):
        """单个文件下载完成回调"""
        task = self.db.get_task(task_id)
        
        if all(f.download_state in (StageState.COMPLETED, StageState.SKIPPED) 
               for f in task.files):
            # 所有文件下载完成，进入校验阶段
            if task.task_type == TaskType.FULL_PIPELINE:
                self._execute_verify_stage(task)
            else:
                task.state = TaskState.COMPLETED
                self.db.update_task(task)
```

---

## 5. 错误处理设计

### 5.1 按阶段错误处理策略

| 阶段 | 失败场景 | 自动处理策略 | 用户干预 |
|------|----------|-------------|----------|
| **下载** | 网络超时/断开 | 自动重试 3 次（指数退避: 1s → 2s → 4s） | 仍失败标记 `PAUSED_DOWNLOAD`，可手动恢复 |
| **下载** | HTTP 4xx 错误（模型不存在） | 不重试，立即标记 `FAILED` | 检查模型 ID 和版本 |
| **下载** | 单文件校验失败 | 删除本地文件，自动重新下载（最多 2 次） | 仍失败标记 `FAILED` |
| **下载** | 磁盘空间不足 | 立即停止所有下载，清理临时文件 | 提示用户清理磁盘 |
| **校验** | 校验值不匹配 | 自动重新下载该文件（进入下载重试逻辑） | — |
| **校验** | 本地文件丢失/损坏 | 自动重新下载 | — |
| **传输** | SSH/rsync 连接失败 | 重试 3 次，指数退避 | 仍失败标记 `PAUSED_TRANSFER` |
| **传输** | 远程磁盘空间不足 | 立即停止传输 | 提示用户清理远程空间 |
| **传输** | 远程权限不足（Permission Denied） | 立即标记 `FAILED` | 提示检查目录权限 |
| **传输** | 远程校验失败 | 重新传输该文件（最多 2 次） | 仍失败标记 `FAILED` |

### 5.2 部分失败处理

```python
class TaskResult:
    """任务执行结果"""
    
    task_id: str
    state: TaskState
    failed_files: list[FailedFileInfo]     # 失败文件列表
    completed_files: list[str]             # 成功完成的文件
    skipped_files: list[str]               # 跳过的文件（用户取消或不需要）
    
    @property
    def is_partial_success(self) -> bool:
        """是否部分成功"""
        return len(self.completed_files) > 0 and len(self.failed_files) > 0
    
    def can_retry_failed(self) -> bool:
        """是否可以仅重试失败的文件"""
        return len(self.failed_files) > 0 and all(
            f.retry_count < MAX_RETRY for f in self.failed_files
        )
```

**功能**:
- 任务完成后，展示 **成功/失败/跳过** 三类文件的清单
- **"重试失败项"按钮**：仅对失败的文件重新执行对应阶段
- **"导出报告"按钮**：导出 JSON/CSV 格式的执行报告，包含每个文件的状态和错误信息

### 5.3 断点续传持久化

```python
class DownloadWorker(QRunnable):
    """下载工作线程"""
    
    def run(self):
        local_path = self.file_info.local_path
        temp_path = local_path.with_suffix('.tmp')
        
        # 检查是否有未完成的临时文件（断点续传）
        resume_byte = 0
        if temp_path.exists():
            resume_byte = temp_path.stat().st_size
        
        headers = {}
        if resume_byte > 0:
            headers['Range'] = f'bytes={resume_byte}-'
        
        try:
            with requests.get(url, headers=headers, stream=True) as resp:
                mode = 'ab' if resume_byte > 0 else 'wb'
                with open(temp_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                        # 每写入一定数据，更新数据库进度（避免频繁 IO，每 1MB 或每 5 秒）
                        self._update_progress(f.tell())
            
            # 下载完成，重命名为正式文件名
            temp_path.rename(local_path)
            self.signals.finished.emit(self.task_id, self.file_info.file_path, True)
            
        except Exception as e:
            # 保存当前进度到数据库
            self.db.update_file_progress(self.task_id, self.file_info.file_path, temp_path.stat().st_size)
            self.signals.error.emit(self.task_id, self.file_info.file_path, str(e))
```

---

## 6. GUI 界面设计

### 6.1 主窗口布局

```
┌──────────────────────────────────────────────────────────────┐
│  [菜单栏]  文件  任务  配置  帮助                              │
├──────────┬───────────────────────────────┬──────────────────┤
│          │                               │                  │
│  向导    │      主内容区                  │    任务队列      │
│  面板    │   (根据当前步骤动态切换)       │    侧边栏        │
│          │                               │                  │
│  ┌────┐  │   ┌─────────────────────┐    │  ┌────────────┐ │
│  │ ①  │  │   │  步骤1: 选择模型源   │    │  │ 任务 #1    │ │
│  │选择 │  │   │                     │    │  │ [下载中 ▓▓]│ │
│  │模型 │  │   │  [HuggingFace]      │    │  ├────────────┤ │
│  └────┘  │   │  [ModelScope]       │    │  │ 任务 #2    │ │
│          │   │                     │    │  │ [等待中 ○○]│ │
│  ┌────┐  │   │  模型ID: [________] │    │  └────────────┘ │
│  │ ②  │  │   │  版本:  [________]  │    │                  │
│  │配置 │  │   │                     │    │  [全部暂停]      │
│  │参数 │  │   │  [下一步]           │    │  [全部取消]      │
│  └────┘  │   └─────────────────────┘    │                  │
│          │                               │  日志预览        │
│  ┌────┐  │   ┌─────────────────────┐    │  ┌────────────┐ │
│  │ ③  │  │   │  步骤2: 配置下载/传输 │    │  │ ...        │ │
│  │确认 │  │   │                     │    │  │ ...        │ │
│  │执行 │  │   │  下载设置:            │    │  └────────────┘ │
│  └────┘  │   │  [ ] 仅下载            │    │                  │
│          │   │  [ ] 下载并传输        │    │                  │
│  ┌────┐  │   │  [ ] 仅传输本地文件    │    │                  │
│  │ ④  │  │   │                     │    │                  │
│  │完成 │  │   │  传输设置:            │    │                  │
│  └────┘  │   │  服务器: [________]    │    │                  │
│          │   │  目标目录: [________]  │    │                  │
│  [历史   │   │                     │    │                  │
│   记录]  │   │  [上一步] [开始执行]   │    │                  │
│          │   └─────────────────────┘    │                  │
│          │                               │                  │
├──────────┴───────────────────────────────┴──────────────────┤
│  状态栏: 就绪 | 总进度: [████████░░░░] 65% | 速度: 12.5 MB/s │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 向导四步流程

#### Step 1: 选择模型

| 控件 | 说明 |
|------|------|
| 模型源选择 | 单选按钮组：HuggingFace / ModelScope |
| 模型 ID 输入 | 文本框，支持自动补全（输入时调用 API 搜索） |
| 版本选择 | 下拉列表，加载该模型的分支/标签列表 |
| 文件过滤 | 文本框，输入过滤模式（如 `*.bin,*.safetensors`），可选 |
| 文件预览 | 树形列表，展示该模型包含的文件和大小（根据过滤条件动态刷新） |
| 下一步 | 验证模型存在性和连通性后进入 Step 2 |

#### Step 2: 配置参数

**下载设置**:
- 任务类型：单选按钮组（仅下载 / 下载并传输 / 仅传输本地文件）
- 本地缓存路径：文件夹选择器（默认应用目录下的 `cache/`）

**传输设置**（仅当选择"下载并传输"或"仅传输"时显示）:
- 服务器选择：下拉列表（从已保存的服务器配置中选择）或"新增服务器"
- 目标目录：文本框（远程服务器的目标路径，如 `/data/models/`）

**代理设置**（可折叠面板）:
- 代理类型：下拉列表（HTTP / SOCKS5 / 不使用）
- 代理地址：文本框（如 `http://127.0.0.1:7890`）
- 加速镜像：文本框（可选，如 HuggingFace 的镜像地址）

#### Step 3: 确认执行

- **文件清单预览**: 树形表格（文件名、大小、本地路径、远程路径、状态）
- **存储空间检查**: 显示本地磁盘剩余空间和远程服务器目标目录的可用空间
- **任务摘要**: 模型信息、文件数量、预计大小、目标服务器
- **操作按钮**: "上一步"、"开始执行"

#### Step 4: 执行监控

- **总体进度**: 大进度条（百分比 + 已下载/总大小）
- **当前速度**: 实时速度（MB/s）
- **预计剩余时间**: ETA
- **文件列表**: 表格展示每个文件的状态（等待中/下载中/校验中/传输中/完成/失败）
- **操作按钮**: "暂停"、"恢复"、"取消"
- **完成状态**: 显示成功/失败/跳过文件数量，"重试失败项"、"导出报告"按钮

### 6.3 任务队列侧边栏

- **任务卡片**: 任务 ID、模型名称、当前阶段、总体进度条
- **状态颜色**: 绿色（完成）、蓝色（进行中）、黄色（暂停）、红色（失败）
- **操作按钮**: 暂停/恢复、取消、查看详情、重试失败项
- **过滤选项**: 全部 / 进行中 / 已完成 / 失败

---

## 7. 数据持久化设计

### 7.1 SQLite 数据库表结构

```sql
-- ============================================
-- 任务主表
-- ============================================
CREATE TABLE tasks (
    id              TEXT PRIMARY KEY,           -- UUID v4
    task_type       TEXT NOT NULL,              -- download_only | transfer_only | full_pipeline
    state           TEXT NOT NULL,              -- pending | downloading | paused_dl | verifying | transferring | paused_tx | completed | failed | cancelled
    model_source    TEXT NOT NULL,              -- huggingface | modelscope
    model_id        TEXT NOT NULL,
    revision        TEXT NOT NULL DEFAULT 'main',
    local_cache_dir TEXT NOT NULL,
    remote_host     TEXT,                       -- 可为 NULL
    remote_path     TEXT,                       -- 可为 NULL
    file_filter     TEXT,                       -- 文件过滤模式
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    error_message   TEXT,                       -- 失败原因摘要
    total_files     INTEGER DEFAULT 0,
    completed_files INTEGER DEFAULT 0,
    total_bytes     INTEGER DEFAULT 0,
    completed_bytes INTEGER DEFAULT 0
);

CREATE INDEX idx_tasks_state ON tasks(state);
CREATE INDEX idx_tasks_created ON tasks(created_at);

-- ============================================
-- 文件清单表
-- ============================================
CREATE TABLE task_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    file_path       TEXT NOT NULL,              -- 相对路径，如 "pytorch_model.bin"
    file_size       INTEGER NOT NULL,           -- 字节
    remote_url      TEXT,                       -- 下载 URL
    expected_hash   TEXT,                       -- 期望的 SHA256/MD5
    hash_algorithm  TEXT,                       -- sha256 | md5
    download_state  TEXT DEFAULT 'pending',     -- pending | downloading | completed | failed | skipped
    download_bytes  INTEGER DEFAULT 0,          -- 已下载字节（断点续传）
    local_path      TEXT,                       -- 本地绝对路径
    verify_state    TEXT DEFAULT 'pending',     -- pending | verifying | completed | failed | skipped
    actual_hash     TEXT,                       -- 实际计算出的 hash
    transfer_state  TEXT DEFAULT 'pending',     -- pending | transferring | completed | failed | skipped
    transfer_bytes  INTEGER DEFAULT 0,          -- 已传输字节（断点续传）
    retry_count     INTEGER DEFAULT 0,          -- 失败重试次数
    error_message   TEXT,
    UNIQUE(task_id, file_path),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_task_files_task ON task_files(task_id);
CREATE INDEX idx_task_files_download ON task_files(download_state);
CREATE INDEX idx_task_files_transfer ON task_files(transfer_state);

-- ============================================
-- 服务器配置表
-- ============================================
CREATE TABLE server_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,       -- 配置名称，如 "GPU-Server-01"
    host            TEXT NOT NULL,
    port            INTEGER DEFAULT 22,
    username        TEXT NOT NULL,
    auth_type       TEXT NOT NULL,              -- password | ssh_key
    encrypted_auth  BLOB NOT NULL,              -- 加密后的凭据
    auth_salt       BLOB NOT NULL,              -- 盐值
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 应用配置表
-- ============================================
CREATE TABLE app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 默认配置项
INSERT INTO app_settings (key, value) VALUES
('download_concurrency', '4'),
('verify_concurrency', '4'),
('transfer_concurrency', '2'),
('theme', 'system'),
('language', 'zh-CN'),
('log_level', 'INFO');

-- ============================================
-- 操作日志表
-- ============================================
CREATE TABLE operation_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT,
    level           TEXT NOT NULL,              -- INFO | WARNING | ERROR | DEBUG
    stage           TEXT NOT NULL,              -- download | verify | transfer | system
    message         TEXT NOT NULL,
    file_path       TEXT,                       -- 关联的文件（如果有）
    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_logs_task ON operation_logs(task_id);
CREATE INDEX idx_logs_timestamp ON operation_logs(timestamp);
```

### 7.2 隐私保护：凭据加密存储

```python
# utils/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os
import keyring

class SecureStorage:
    """安全的凭据存储（AES-256-GCM）
    
    设计原则:
    1. 主密钥存储在系统钥匙串（Windows Credential / macOS Keychain / Linux Secret Service）
    2. 数据库中存储的是加密后的凭据 + nonce + 盐值
    3. 使用 AES-256-GCM 提供认证加密（同时保证机密性和完整性）
    4. 即使数据库文件泄露，没有系统钥匙串的主密钥也无法解密
    """
    
    SERVICE_NAME = "model-transfer-tool"
    MASTER_KEY_ID = "master_key"
    
    @classmethod
    def _get_or_create_master_key(cls) -> bytes:
        """获取或创建主密钥（256-bit）"""
        key_b64 = keyring.get_password(cls.SERVICE_NAME, cls.MASTER_KEY_ID)
        if key_b64 is None:
            key = os.urandom(32)  # 256-bit
            key_b64 = base64.urlsafe_b64encode(key).decode()
            keyring.set_password(cls.SERVICE_NAME, cls.MASTER_KEY_ID, key_b64)
        return base64.urlsafe_b64decode(key_b64)
    
    @classmethod
    def encrypt(cls, plaintext: str) -> tuple[bytes, bytes, bytes]:
        """加密凭据
        
        Returns:
            (加密数据, nonce, 盐值)
        """
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(cls._get_or_create_master_key())
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # GCM 推荐 96-bit nonce
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return ciphertext, nonce, salt
    
    @classmethod
    def decrypt(cls, ciphertext: bytes, nonce: bytes, salt: bytes) -> str:
        """解密凭据"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(cls._get_or_create_master_key())
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
```

---

## 8. 打包与部署方案

### 8.1 绿色便携目录结构

```
ModelTransferTool/
├── ModelTransferTool.exe          # 主程序入口（PyInstaller 打包）
├── config/                        # 用户配置（启动时自动创建）
│   ├── settings.json              # 应用设置（代理、并发度、主题等）
│   └── servers.json               # 服务器配置（加密存储）
├── data/                          # SQLite 数据库
│   └── tasks.db
├── cache/                         # 模型缓存目录
│   └── huggingface/
│       └── models--org--model/
│           ├── pytorch_model.bin
│           └── config.json
│   └── modelscope/
│       └── org/model/
├── logs/                          # 日志文件
│   ├── app_2026-06-01.log
│   └── app_2026-06-02.log
└── resources/                     # 静态资源
    ├── icons/
    │   ├── app.ico
    │   └── status/
    └── styles/
        └── dark.qss
```

### 8.2 打包配置

**使用 PyInstaller 单目录模式**:

```python
# build.py
import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--name=ModelTransferTool',
    '--onedir',                    # 单目录模式（非单文件，启动更快）
    '--windowed',                  # GUI 应用，不显示控制台
    '--icon=resources/icons/app.ico',
    '--add-data=resources;resources',
    '--hidden-import=PyQt6.sip',
    '--hidden-import=cryptography',
    '--hidden-import=keyring.backends.Windows',
    '--hidden-import=huggingface_hub',
    '--hidden-import=modelscope',
    '--clean',
    '--noconfirm',
])
```

### 8.3 运行时环境检测

```python
# main.py
import sys
import os
import shutil

def setup_environment():
    """配置运行时环境"""
    # 检测是否在打包环境中运行
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建必要的目录
    for subdir in ['config', 'data', 'cache', 'logs']:
        os.makedirs(os.path.join(base_dir, subdir), exist_ok=True)
    
    # 设置环境变量
    os.environ['APP_BASE_DIR'] = base_dir
    os.environ['APP_LOG_DIR'] = os.path.join(base_dir, 'logs')
    
    # 检查 rsync 是否可用
    if not shutil.which('rsync'):
        print("警告: 未检测到 rsync，请安装 Git for Windows 或 Cygwin")
        # GUI 启动后显示友好提示
    
    return base_dir

if __name__ == '__main__':
    base_dir = setup_environment()
    # 启动 GUI 应用...
```

---

## 9. 关键决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| GUI 框架 | PyQt6 | 组件丰富（树形/表格/分栏），线程模型成熟，专业级界面支持 |
| 打包工具 | PyInstaller | 成熟稳定，支持单目录模式，对 PyQt6 和加密库兼容好 |
| 数据库 | SQLite | 零配置，单文件存储，Python 内置支持 |
| 下载库 | `huggingface_hub` + `modelscope` SDK | 官方 SDK，支持断点续传和校验值获取 |
| 传输协议 | rsync (subprocess) | 用户指定需求，增量传输效率高，断点续传原生支持 |
| 加密方案 | PBKDF2 + AES-256-GCM | 认证加密方案，`cryptography` 库成熟，同时保证机密性和完整性 |
| 任务调度 | QThreadPool + 信号槽 | Qt 原生线程池，与 GUI 集成好，避免手动线程管理 |
| 并发模型 | 阶段串行、内部并行 | 避免下载和传输竞争带宽，各阶段内部最大化并行效率 |

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| rsync 在 Windows 上不易获取 | 高 | 启动时检测并提示用户安装 Git for Windows（自带 rsync）或 Cygwin |
| 大模型（100GB+）下载磁盘空间不足 | 高 | 下载前检查磁盘空间，下载中实时监控，不足时暂停并提示 |
| 系统钥匙串不可用（某些企业环境） | 中 | 降级方案：使用用户密码派生密钥（启动时询问） |
| HuggingFace/ModelScope API 变更 | 中 | 封装 SDK 调用，统一异常处理，预留版本适配层 |
| 多线程并发导致 SQLite 锁竞争 | 低 | 使用 WAL 模式，写操作集中在主线程，工作线程只读 |
| 打包体积过大（>100MB） | 低 | PyInstaller 单目录模式支持增量更新，可考虑 Nuitka 优化 |

---

## 11. 验收标准

### 11.1 功能验收

- [ ] 可以从 HuggingFace 下载指定模型和版本到本地
- [ ] 可以从 ModelScope 下载指定模型和版本到本地
- [ ] 下载过程中断（关闭应用），重启后可从断点继续
- [ ] 下载完成后自动校验文件完整性，失败自动重试
- [ ] 可以将本地缓存的模型通过 rsync 传输到远程服务器
- [ ] 传输过程中断，重启后可从断点继续
- [ ] 支持创建多个任务，任务队列按顺序执行
- [ ] 支持暂停/恢复/取消任务
- [ ] 支持失败文件单独重试，不重复已成功文件
- [ ] 服务器密码/SSH key 加密存储，不泄露明文
- [ ] 绿色便携目录，解压即用，无系统依赖

### 11.2 性能验收

- [ ] 下载阶段 CPU 占用 < 10%（纯 I/O 场景）
- [ ] UI 在下载/传输过程中保持 60fps 响应
- [ ] 1000 个文件的任务列表加载时间 < 1 秒
- [ ] SQLite 数据库操作（任务创建/更新）< 10ms

### 11.3 兼容性验收

- [ ] Windows 10/11 64位正常运行
- [ ] 支持高分屏（DPI 缩放）
- [ ] 支持深色/浅色主题切换

---

**文档版本**: v1.0
**最后更新**: 2026-06-01
**作者**: AI Assistant
**评审状态**: 待用户评审
