# easy-modelengine — model-transfer-tool

模型下载与远程传输桌面工具(PyQt6)。核心流程:用户通过向导(wizard)选择模型来源与目标,系统将模型从 HuggingFace/ModelScope/本地目录下载到本地缓存,可选 rsync 传输到远程服务器。

## Language

**Task**:
一个工作单元——从 HuggingFace/ModelScope/本地目录将模型文件下载到本地缓存,可选再传输到远程服务器。
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
Task 内单个文件的元数据——路径、大小、期望哈希、各阶段(下载/校验/传输)状态与进度。
_Avoid_: file entry, file row

**wizard**:
四步引导面板——收集模型来源、版本、目标服务器等原始选择,最终发射 TaskDraft。
_Avoid_: setup wizard, form

**Server profile**:
服务器连接配置——主机、用户名、端口、SSH 密钥或密码;加密保存在数据库中。当前尚无消费者(wizard 与 Task intake 未读取)。
_Avoid_: server config, server settings

**Proxy**:
下载代理配置——启用开关、http/https/socks5 地址、镜像开关;以键值对存在 app_settings。
_Avoid_: network settings, mirror config