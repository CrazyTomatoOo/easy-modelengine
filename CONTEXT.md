# easy-modelengine — model-transfer-tool

模型下载与远程传输桌面工具(PyQt6)。核心流程:用户通过向导(wizard)选择模型来源与目标,系统将模型从 HuggingFace/ModelScope/本地目录下载到本地缓存,可选 rsync 传输到远程服务器。

## Language

**Task**:
一个工作单元——从 HuggingFace/ModelScope/本地目录将模型文件下载到本地缓存,可选再传输到远程服务器。生命周期:任意文件失败即 FAILED(停止后续阶段);下载/传输阶段可暂停/恢复(断点续传)与取消(丢弃,保留已下载部分)。
_Avoid_: job, download job

**TaskConfig**:
一个 Task 的完整配置——类型、来源、模型标识、revision、缓存目录、远程目标、文件列表。
_Avoid_: task dict, task params

**TaskDraft**:
wizard 各步骤产生的原始选择快照,未做任何业务解释(不含 task_type 映射、不含文件列表);由 Task intake 消费。
_Avoid_: form data, wizard result

**Task intake**:
core 中的深层模块——把 TaskDraft 变成 TaskConfig:校验、本地目录扫描、源文件列表、TaskFile 组装;通过注入的源解析器(默认 HuggingFace/ModelScope/LocalDir 三种策略)完成列表。
_Avoid_: task builder, task service, task handler

**TaskFile**:
Task 内单个文件的元数据——路径、大小、期望哈希、各阶段(下载/校验/传输)状态与进度。校验状态显式区分「通过」与「未校验」:无源校验和的文件标为未校验,不做哈希比对,绝不静默当作通过。
_Avoid_: file entry, file row

**源校验和**:
平台在文件元数据中提供的期望哈希——HuggingFace LFS 为 sha256,ModelScope 为 Sha256;有它才能做哈希校验,无它则该文件「未校验」。本地目录不属任何平台,永远没有源校验和,其完整性靠传输侧保证(远程校验,以本地实时哈希为期望)。
_Avoid_: expected hash(实现层字段名),checksum

**远程校验**:
传输阶段完成后对远端副本的哈希比对(sha256sum 回读),失败即任务 FAILED(远端残件保留,rsync 可续传复用)。本地源无源校验和,以本地文件实时哈希为期望值——语义是「远端副本与本地源一致」,而非平台背书。
_Avoid_: server check, remote checksum

**wizard**:
四步引导面板——收集模型来源、版本、目标服务器等原始选择,最终发射 TaskDraft。
_Avoid_: setup wizard, form

服务器连接配置——主机、端口、用户名、认证类型与加密凭据;以 `server_configs` 表持久化。wizard 的服务器下拉与 Task 传输阶段按 name 引用它;SSH 密钥认证走 rsync,密码认证走 SFTP 适配器(paramiko)。
_Avoid_: server config, server settings
服务器连接配置——主机、端口、用户名、认证类型与加密凭据;以 `server_configs` 表持久化。wizard 的服务器下拉与 Task 传输阶段按 name 引用它;SSH 密钥认证可用,密码认证待 rsync 密码通道(候选 6)。
_Avoid_: server config, server settings

**Proxy**:
下载代理配置——启用开关、http/https 地址;以 `core/proxy_config.py` 的 **ProxyConfig** 类型化保存(load/save/校验);列表与下载阶段的策略构造共用它。镜像源配置(旧 mirror_hf/mirror_ms)已删除——从未有消费者。
_Avoid_: network settings, mirror config