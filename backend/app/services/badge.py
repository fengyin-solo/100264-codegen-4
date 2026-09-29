"""员工通行证业务规则。

口径（按值班员的查询习惯固化）：
1. 同一员工（工号相同）被多个单位重复授权时，只认办理时间最近的那张，
   旧授权一律不再参与筛选，冲突以新证为准。
2. 已过期的通行证先过滤掉；门禁权限与所在岗位不符的也先过滤掉。
3. 参与筛选的通行证按有效期止由近到远排列，临期的排最前。
过滤与去重结果都通过 excluded 明示，不做静默丢弃。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "badge"

PERMISSION_LEVELS = ["机坪门禁", "候机楼门禁", "公共区域"]

# 岗位与门禁权限的对应关系：允许持有的权限必须落在岗位对应集合里。
# 机坪作业岗位必须有机坪门禁；客运、安检类岗位持候机楼门禁即可；
# 行政后勤岗位只允许公共区域权限。
POST_PERMISSIONS: dict[str, set[str]] = {
    "机坪装卸员": {"机坪门禁"},
    "机坪巡查员": {"机坪门禁"},
    "牵引车司机": {"机坪门禁"},
    "加油员": {"机坪门禁"},
    "廊桥操作员": {"机坪门禁"},
    "客运服务员": {"机坪门禁", "候机楼门禁"},
    "值机员": {"候机楼门禁"},
    "配餐调度员": {"候机楼门禁", "机坪门禁"},
    "行政文员": {"公共区域"},
}

# 概览里“临期待办”的提前量：有效期不足 30 天即进入待办。
EXPIRING_SOON_DAYS = 30


def _today() -> date:
    return date.today()


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_active(row: dict[str, Any], today: date) -> bool:
    start = _parse_date(row.get("有效期起"))
    end = _parse_date(row.get("有效期止"))
    return (start is None or start <= today) and (end is None or end >= today)


def _issued_key(row: dict[str, Any]) -> tuple[date, int]:
    """办理时间排序键；办理时间缺失或不可解析时按最早处理，避免脏数据被当成最新。"""
    issued = _parse_date(row.get("办理时间")) or date.min
    return issued, int(row.get("id", 0))


class BadgeService:
    # ---- 快照：每次查询都重算，保证概览待办数跟着明细变化 -----------------
    def snapshot(self) -> dict[str, Any]:
        """把原始通行证清单去重、判定、排序，返回一份可直接给前端的快照。"""
        today = _today()
        raw_rows = store.rows(MODULE)

        latest: dict[str, dict[str, Any]] = {}
        superseded: list[dict[str, Any]] = []
        for row in raw_rows:
            emp_no = str(row.get("工号", "")).strip()
            if not emp_no:
                # 没有工号无法判断重复，直接放行给后续过期/岗位校验。
                emp_no = f"__no_emp__{row.get('id')}"
            current = latest.get(emp_no)
            if current is None or _issued_key(row) > _issued_key(current):
                if current is not None:
                    superseded.append(current)
                latest[emp_no] = row
            else:
                superseded.append(row)

        items: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []

        for row in superseded:
            holder = latest.get(str(row.get("工号", "")).strip(), {})
            excluded.append(self._excluded_view(
                row,
                "重复授权",
                f"同一工号存在更新办理（{holder.get('通行证编号', '—')}，"
                f"办理时间 {holder.get('办理时间', '—')}），以新证为准，本张旧授权不参与筛选",
            ))

        for row in latest.values():
            end = _parse_date(row.get("有效期止"))
            if not _is_active(row, today):
                reason_detail = f"有效期至 {row.get('有效期止', '—')}，已过期"
                excluded.append(self._excluded_view(row, "已过期", reason_detail))
                continue
            level = str(row.get("门禁权限", "")).strip()
            post = str(row.get("岗位", "")).strip()
            allowed = POST_PERMISSIONS.get(post)
            if allowed is not None and level not in allowed:
                reason_detail = (
                    f"岗位「{post}」允许的门禁权限为{'、'.join(sorted(allowed))}，"
                    f"本证为「{level or '未填'}」，权限与岗位不符"
                )
                excluded.append(self._excluded_view(row, "权限与岗位不符", reason_detail))
                continue
            items.append(self._item_view(row, today))

        # 有效期止越近越靠前；日期缺失的排最后；同日期按通行证编号稳定排序。
        items.sort(key=lambda item: (
            item["_expiry_sort"] is None,
            item["_expiry_sort"] or "9999-12-31",
            str(item.get("通行证编号", "")),
        ))
        excluded.sort(key=lambda view: (
            view["过滤类别"],
            view["办理时间"] or "",
            view["id"],
        ))

        stats = self._build_stats(items, excluded)
        facets = self._build_facets(items)
        return {"items": items, "excluded": excluded, "stats": stats, "facets": facets}

    def list_entries(
        self,
        *,
        unit: str | None = None,
        level: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[dict[str, Any], int]:
        """按单位、权限级别筛选有效通行证；两个条件互相独立，互不覆盖。"""
        snap = self.snapshot()
        rows = snap["items"]
        if unit:
            rows = [row for row in rows if unit in str(row.get("所属单位", ""))]
        if level:
            rows = [row for row in rows if row.get("门禁权限") == level]
        if keyword:
            key = keyword.strip()
            rows = [
                row for row in rows
                if key in str(row.get("姓名", "")) or key in str(row.get("通行证编号", ""))
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_items = [dict(row) for row in rows[start:start + size]]
        result = {
            "items": page_items,
            "total": total,
            "excluded": snap["excluded"],
            "stats": snap["stats"],
            "facets": snap["facets"],
        }
        return result, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """读取单张通行证：有效证给出到期提示，失效证写明被过滤的原因。"""
        snap = self.snapshot()
        for row in snap["items"]:
            if int(row.get("id", 0)) == entry_id:
                return dict(row)
        for row in snap["excluded"]:
            if int(row.get("id", 0)) == entry_id:
                view = dict(row)
                view["参与筛选"] = False
                return view
        return None

    def overview_counts(self) -> dict[str, int]:
        """运营概览用：待办/异常以明细口径实时计算，重复授权旧证不重复计数。"""
        snap = self.snapshot()
        expired = sum(1 for row in snap["excluded"] if row["过滤类别"] == "已过期")
        mismatched = sum(1 for row in snap["excluded"] if row["过滤类别"] == "权限与岗位不符")
        expiring = sum(1 for row in snap["items"] if bool(row["临期预警"]))
        return {
            "created": len(store.rows(MODULE)),
            "pending": expired + mismatched + expiring,
            "abnormal": expired + mismatched,
        }

    # ---- 视图组装 ---------------------------------------------------------
    @staticmethod
    def _excluded_view(row: dict[str, Any], category: str, detail: str) -> dict[str, Any]:
        view = {key: value for key, value in row.items() if not key.startswith("_")}
        view.update({
            "参与筛选": False,
            "过滤类别": category,
            "过滤原因": detail,
        })
        return view

    @staticmethod
    def _item_view(row: dict[str, Any], today: date) -> dict[str, Any]:
        view = dict(row)
        end = _parse_date(row.get("有效期止"))
        days_left = (end - today).days if end else None
        if days_left is None:
            warn = False
            warn_label = "有效期未登记"
        elif days_left < 0:
            warn = False
            warn_label = "已过期"
        elif days_left <= EXPIRING_SOON_DAYS:
            warn = True
            warn_label = f"{days_left} 天后到期"
        else:
            warn = False
            warn_label = f"{days_left} 天后到期"
        view.update({
            "参与筛选": True,
            "剩余天数": days_left,
            "临期预警": warn,
            "到期提示": warn_label,
            "_expiry_sort": end.isoformat() if end else None,
        })
        return view

    @staticmethod
    def _build_stats(items: list[dict[str, Any]], excluded: list[dict[str, Any]]) -> list[dict[str, Any]]:
        expired = sum(1 for row in excluded if row["过滤类别"] == "已过期")
        mismatched = sum(1 for row in excluded if row["过滤类别"] == "权限与岗位不符")
        superseded = sum(1 for row in excluded if row["过滤类别"] == "重复授权")
        return [
            {"label": "有效通行证", "value": len(items)},
            {"label": f"{EXPIRING_SOON_DAYS}天内到期", "value": sum(1 for row in items if row["临期预警"] is True)},
            {"label": "过期/权限不符", "value": expired + mismatched},
            {"label": "重复授权旧证", "value": superseded},
        ]

    @staticmethod
    def _build_facets(items: list[dict[str, Any]]) -> dict[str, list[str]]:
        """筛选项候选：单位只列一级（“-”前的单位名），按名称去重排序。"""
        units = {str(row.get("所属单位", "")).split("-", 1)[0] for row in items}
        levels = {str(row.get("门禁权限", "")) for row in items}
        return {
            "units": sorted(unit for unit in units if unit),
            "levels": [level for level in PERMISSION_LEVELS if level in levels],
        }
