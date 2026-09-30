"""员工通行证（机坪门禁）接口：按单位 / 门禁级别定位，结果自带过滤说明。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import PassbadgePageResult
from app.services.passbadge import LEVELS, PassbadgeService

router = APIRouter(prefix="/api/passbadge", tags=["员工通行证"])

service = PassbadgeService()


@router.get("", response_model=PassbadgePageResult)
def list_passes(
    unit: str | None = Query(default=None, description="按所属单位定位，切换单位不影响已选级别"),
    level: str | None = Query(default=None, description="按门禁权限级别筛选：机坪 / 候机隔离区 / 管控区"),
    keyword: str | None = Query(default=None, description="按姓名或通行证编号检索"),
    page: int = 1,
    size: int = 100,
) -> PassbadgePageResult:
    """先过滤（过期、岗位不符、重复授权旧证）再按有效期临近程度排序。

    取不到数据不是错误：返回空 items，同时在 excluded 里写明每条被过滤的原因。
    """
    if size > 500:
        raise HTTPException(status_code=400, detail="每页最多 500 条，请缩小分页范围")
    if level is not None and level not in LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"门禁级别「{level}」不合法，可选：{' / '.join(LEVELS)}",
        )
    result = service.list_passes(unit=unit, level=level, keyword=keyword, page=page, size=size)
    return PassbadgePageResult(**result)


@router.get("/stats")
def pass_stats() -> dict[str, int]:
    """通行证待办与过滤量，运营概览卡片直接用这份口径。"""
    return service.stats()


@router.get("/{pass_id}")
def get_pass(pass_id: int) -> dict[str, object]:
    """读取单张通行证；被过滤掉的证也可查，但会带上不可用原因。"""
    entry = service.detail(pass_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"通行证 {pass_id} 不存在或已注销")
    return entry
