"""员工通行证接口：按单位、门禁权限定位通行证，并明示被过滤的记录。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import BadgeListResult
from app.services.badge import BadgeService

router = APIRouter(prefix="/api/badge", tags=["员工通行证"])

service = BadgeService()


@router.get("", response_model=BadgeListResult)
def list_entries(
    unit: str | None = Query(default=None, description="所属单位（按单位名包含匹配，如“特种车辆保障部”）"),
    level: str | None = Query(default=None, description="门禁权限级别：机坪门禁、候机楼门禁、公共区域"),
    keyword: str | None = Query(default=None, description="按姓名或通行证编号检索"),
    page: int = 1,
    size: int = 20,
) -> dict[str, object]:
    """筛选有效通行证。

    返回 items（已按有效期临近程度排序）、total、excluded（被去重或过滤的记录及原因）、
    stats（概览统计）与 facets（单位、权限级别候选）。没有匹配数据时返回空列表，不报错。
    """
    if page < 1:
        raise HTTPException(status_code=400, detail="页码从 1 开始")
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    payload, total = service.list_entries(unit=unit, level=level, keyword=keyword, page=page, size=size)
    payload["page"] = page
    payload["size"] = size
    return payload


@router.get("/facets")
def list_facets() -> dict[str, object]:
    """筛选项候选：单位与权限级别，供前端先选条件再筛通行证。"""
    snap = service.snapshot()
    return {"facets": snap["facets"], "stats": snap["stats"]}


@router.get("/export")
def export_entries(
    unit: str | None = None,
    level: str | None = None,
) -> dict[str, object]:
    """导出当前筛选口径下的通行证清单，过滤明细一并导出。"""
    payload, total = service.list_entries(unit=unit, level=level, page=1, size=10000)
    return {
        "module": "badge",
        "total": total,
        "items": payload["items"],
        "excluded": payload["excluded"],
    }


@router.get("/{entry_id}")
def get_entry(entry_id: int) -> dict[str, object]:
    """读取单张通行证明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"通行证 {entry_id} 不存在或已注销")
    return entry
