"""员工通行证（机坪门禁）业务规则。

口径集中在这里，列表与运营概览共用同一份结果：
1. 同一员工被重复授权（含跨单位）时，以最近办理的那张为准，旧证不再参与筛选；
2. 已经过期、门禁级别与所在岗位不符的通行证先过滤掉，并附过滤原因；
3. 剩余通行证按有效期临近程度排序，30 天内到期计入待办。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.store import store

MODULE = "passbadge"

# 门禁权限级别，由低到高；筛选下拉与校验都以此为准。
LEVELS = ["机坪", "候机隔离区", "管控区"]

# 临近到期阈值：有效期不足 30 天的通行证进入待续办待办。
RENEW_WINDOW_DAYS = 30

# 各岗位允许持有的门禁级别；不在表内的岗位需要人工核对，一律先拦下。
POST_ALLOWED_LEVELS: dict[str, set[str]] = {
    "机坪装卸员": {"机坪", "管控区"},
    "客梯车操作员": {"机坪", "管控区"},
    "廊桥操作员": {"机坪", "管控区"},
    "机务维修员": {"机坪", "管控区"},
    "加油员": {"机坪", "管控区"},
    "货运司机": {"候机隔离区", "管控区"},
    "运行指挥员": {"管控区"},
    "安全检查员": {"管控区"},
}


def _parse_date(value: Any) -> date | None:
    """把 'YYYY-MM-DD' 解析成日期；缺失或格式不对时返回 None，由调用方归类。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class PassbadgeService:
    # -- 核心管线：去重 → 过滤 → 排序 ----------------------------------------

    def _organize(
        self, today: date
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """返回（有效通行证, 被排除通行证）。

        有效行附带 days_to_expiry / pending 派生字段；被排除行附带「排除原因」。
        """
        rows = store.rows(MODULE)

        # 1) 同一员工只保留最近办理的一张：按（办理日期, id）升序遍历，后出现的赢。
        representatives: dict[str, dict[str, Any]] = {}
        superseded: list[dict[str, Any]] = []
        ordered = sorted(
            rows,
            key=lambda row: (
                _parse_date(row.get("办理日期")) or date.min,
                int(row.get("id", 0)),
            ),
        )
        for row in ordered:
            name = str(row.get("姓名") or "").strip()
            older = representatives.get(name)
            if older is not None:
                superseded.append(
                    self._as_excluded(
                        older,
                        "重复授权：同一员工存在多张通行证，"
                        f"以最近办理的 {row.get('通行证编号')}（{row.get('所属单位')}，"
                        f"{row.get('办理日期')}）为准，本证不再参与筛选",
                    )
                )
            representatives[name] = row

        # 2) 过期、岗位与门禁级别不符的先过滤掉。
        valid: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = list(superseded)
        for row in representatives.values():
            name = str(row.get("姓名") or "").strip()
            level = str(row.get("门禁级别") or "").strip()
            post = str(row.get("所在岗位") or "").strip()
            expiry = _parse_date(row.get("有效期至"))

            if not name:
                excluded.append(self._as_excluded(row, "证件信息缺失：未登记持证人姓名"))
                continue
            if expiry is None:
                excluded.append(self._as_excluded(row, "有效期缺失或日期格式无法识别，已拦下待人工核对"))
                continue
            if expiry < today:
                excluded.append(
                    self._as_excluded(row, f"已过期：有效期至 {row.get('有效期至')}")
                )
                continue
            allowed = POST_ALLOWED_LEVELS.get(post)
            if allowed is None:
                excluded.append(
                    self._as_excluded(row, f"岗位「{post}」未维护允许的门禁级别，需人工核对后再放行")
                )
                continue
            if level not in allowed:
                excluded.append(
                    self._as_excluded(
                        row, f"门禁权限与岗位不符：{post}不应持有「{level}」级别"
                    )
                )
                continue

            days = (expiry - today).days
            entry = dict(row)
            entry["days_to_expiry"] = days
            entry["pending"] = days <= RENEW_WINDOW_DAYS
            valid.append(entry)

        # 3) 有效期越临近越靠前；同日到期按姓名稳定排序。
        valid.sort(key=lambda row: (row["days_to_expiry"], str(row.get("姓名"))))
        return valid, excluded

    @staticmethod
    def _as_excluded(row: dict[str, Any], reason: str) -> dict[str, Any]:
        entry = dict(row)
        entry["排除原因"] = reason
        return entry

    # -- 对外查询 -------------------------------------------------------------

    def list_passes(
        self,
        *,
        unit: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 50,
        today: date | None = None,
    ) -> dict[str, Any]:
        today = today or date.today()
        valid, excluded = self._organize(today)

        units = self.list_units()

        def matches(row: dict[str, Any], *, by_level: bool) -> bool:
            if unit and str(row.get("所属单位") or "").strip() != unit:
                return False
            if by_level and level and str(row.get("门禁级别") or "").strip() != level:
                return False
            if keyword:
                haystack = f"{row.get('姓名', '')}{row.get('通行证编号', '')}"
                if keyword not in haystack:
                    return False
            return True

        items = [row for row in valid if matches(row, by_level=True)]
        # 过滤说明跟随单位/姓名检索，但级别筛选不作用于“已被过滤”的条目，
        # 否则切换级别时被排除原因会被藏起来。
        filtered_out = [row for row in excluded if matches(row, by_level=False)]

        total = len(items)
        start = max(page - 1, 0) * size
        window = items[start:start + size]

        # 待办按“全部有效通行证”口径统计，保证运营概览不随筛选条件抖动。
        pending_total = sum(1 for row in valid if row["pending"])

        return {
            "items": window,
            "total": total,
            "page": page,
            "size": size,
            "units": units,
            "levels": list(LEVELS),
            "excluded": filtered_out,
            "pending_total": pending_total,
        }

    def list_units(self) -> list[str]:
        """单位下拉：取数据里出现过的单位并按首次出现顺序去重。"""
        units: list[str] = []
        for row in store.rows(MODULE):
            name = str(row.get("所属单位") or "").strip()
            if name and name not in units:
                units.append(name)
        return units

    def stats(self, today: date | None = None) -> dict[str, int]:
        """运营概览口径：待续办数跟有效明细走，异常量即被过滤掉的条目数。"""
        today = today or date.today()
        valid, excluded = self._organize(today)
        return {
            "total": len(valid),
            "pending": sum(1 for row in valid if row["pending"]),
            "excluded": len(excluded),
            "renew_window_days": RENEW_WINDOW_DAYS,
        }

    def detail(self, pass_id: int, today: date | None = None) -> dict[str, Any] | None:
        """单张通行证明细：有效证给剩余天数，失效证给具体失效原因。"""
        today = today or date.today()
        valid, excluded = self._organize(today)

        for row in valid:
            if int(row.get("id", 0)) == pass_id:
                entry = dict(row)
                entry["当前状态"] = "有效"
                return entry

        for row in excluded:
            if int(row.get("id", 0)) == pass_id:
                entry = dict(row)
                expiry = _parse_date(row.get("有效期至"))
                if expiry is not None and expiry >= today:
                    entry["days_to_expiry"] = (expiry - today).days
                entry["当前状态"] = f"不可用：{row['排除原因']}"
                return entry

        return None
