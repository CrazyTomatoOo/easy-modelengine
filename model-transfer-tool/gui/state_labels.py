"""状态呈现注册表 —— Task/Stage 状态的标签/颜色/分类单一事实源。

三个面板(main_window 的状态文本、task_details_dialog 的校验状态、
task_panel 的过滤与暂停)统一查这张表;key 一律是枚举值字符串,
逻辑键控 key 而非译文——译文改名不会静默破坏过滤/暂停/计数(Q2A)。

Task 状态带 category(进行中/已完成/失败)供面板过滤;Stage 状态只有
标签与颜色(校验上下文)。颜色沿用既有面板配色(Q3A 一处定义)。
"""

from dataclasses import dataclass

from core.task_config import TaskState, StageState


@dataclass(frozen=True)
class Presentation:
    label: str
    color: str
    category: str = ""  # 仅 Task 状态:进行中 | 已完成 | 失败


TASK_STATE_PRESENTATION: dict[str, Presentation] = {
    TaskState.PENDING.value: Presentation("等待中", "#6B7280", "进行中"),
    TaskState.DOWNLOADING.value: Presentation("下载中", "#2563EB", "进行中"),
    TaskState.PAUSED_DOWNLOAD.value: Presentation("已暂停", "#B45309", "进行中"),
    TaskState.VERIFYING.value: Presentation("校验中", "#2563EB", "进行中"),
    TaskState.TRANSFERRING.value: Presentation("传输中", "#2563EB", "进行中"),
    TaskState.PAUSED_TRANSFER.value: Presentation("已暂停", "#B45309", "进行中"),
    TaskState.COMPLETED.value: Presentation("已完成", "#16A34A", "已完成"),
    TaskState.FAILED.value: Presentation("失败", "#DC2626", "失败"),
    TaskState.CANCELLED.value: Presentation("已取消", "#6B7280", "失败"),
}

STAGE_STATE_PRESENTATION: dict[str, Presentation] = {
    "pending": Presentation("待校验", "#6B7280"),
    StageState.NOT_STARTED.value: Presentation("未开始", "#6B7280"),
    StageState.IN_PROGRESS.value: Presentation("校验中", "#2563EB"),
    StageState.COMPLETED.value: Presentation("通过", "#16A34A"),
    StageState.FAILED.value: Presentation("失败", "#DC2626"),
    StageState.SKIPPED.value: Presentation("未校验", "#B45309"),
}