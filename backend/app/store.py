"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS

# 模块名到中文看板名的映射：概览表格直接展示业务名称，不再暴露英文目录名。
MODULE_LABELS: dict[str, str] = {
    "flightstand": "机位分配",
    "marshalling": "引导入位",
    "bridge": "廊桥对接",
    "baggage": "行李装卸",
    "catering": "航食配餐",
    "fueling": "航油加注",
    "deicing": "除冰作业",
    "lavatory": "清水排污",
    "pushback": "推出开车",
    "gse": "地面设备",
    "cargo": "货物装卸",
    "clearance": "放行签派",
    "turnaround": "过站保障",
    "ramp": "机坪巡查",
    "weather2": "航空气象",
    "vehicle": "特种车辆",
    "staffshift": "人员排班",
    "runway": "跑道灯光",
    "emergencyplan": "应急处置",
    "qualitycheck": "质量监察",
    "badge": "员工通行证",
}


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        # 通行证的待办、异常以过滤后的明细口径实时计算（过期、权限不符、临期），
        # 其余模块沿用记录上的 pending/abnormal 标记。
        from app.services.badge import MODULE as BADGE_MODULE
        from app.services.badge import BadgeService

        badge_counts = BadgeService().overview_counts()
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            if name == BADGE_MODULE:
                counts = badge_counts
                modules.append({
                    "name": MODULE_LABELS.get(name, name),
                    "module": name,
                    "created": counts["created"],
                    "pending": counts["pending"],
                    "abnormal": counts["abnormal"],
                })
                continue
            modules.append({
                "name": MODULE_LABELS.get(name, name),
                "module": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
