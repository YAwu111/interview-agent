from fastapi import APIRouter

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/usage")
async def get_usage() -> dict:
    """用量查询接口位：统计存储落地前返回零值占位。鉴权由 gateway 聚合时注入。"""
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
