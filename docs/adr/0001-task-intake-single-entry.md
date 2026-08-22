# Task intake 是任务进入系统的唯一接口

模型传输工具的任务形状逻辑原先分散在向导与主窗口的重复代码块中——一次「完成」点击会创建 4 个任务(`task_created` 双连接 × 双代码块),本地模型选择分支在层叠合并中丢失。我们决定新建 core 中的 **Task intake** 模块,作为从 **TaskDraft**(向导发射的原始选择快照)到 **TaskConfig** 的唯一转换接口:校验、本地目录扫描、源文件列表与 TaskFile 组装全部收进该模块;源解析通过注入式解析器完成(默认 HuggingFace / ModelScope / LocalDir 三策略);校验失败抛 `DraftValidationError`,由 GUI 捕获展示。原因:任务形状逻辑集中在单一深层模块、无 Qt 依赖、可经单一接口测试,结构性漂移(如本地分支丢失)不再可能。

## 考虑过的方案

- **薄 intake**:只组装 TaskConfig,校验与本地扫描留在 widget —— 逻辑仍留在 bug 实际所在层。
- **GUI 构造 downloader 传入**:接口未实质收敛,GUI 仍认识具体下载类。
- **保留 dict 契约**:无类型,重复代码块可以再次各自漂移。

## 后果

- GUI(wizard / 主窗口)不再构造 downloader,不再映射任务类型字符串。
- 代理配置统一、校验/哈希联动不属于本决策,分别归后续 ProxyConfig 与任务生命周期工作。
- `docs/adr/0001` 之后,任务创建只经 Task intake 一个路径;新入口(CLI、脚本)复用同一模块。