from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.db.models.usage import UsageDaily
from app.data.db.session import get_session

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/usage")
async def get_usage(
    request: Request,
    session: AsyncSession = Depends(get_session),
    days: int = 7,
) -> dict:
    since = date.today() - timedelta(days=max(1, days) - 1)
    rows = (
        await session.execute(
            select(
                UsageDaily.model,
                UsageDaily.date,
                func.sum(UsageDaily.total_tokens),
                func.sum(UsageDaily.calls),
                func.sum(UsageDaily.latency_sum_ms),
            )
            .where(UsageDaily.user_id == request.state.user_id, UsageDaily.date >= since)
            .group_by(UsageDaily.model, UsageDaily.date)
            .order_by(UsageDaily.date.desc(), UsageDaily.model)
        )
    ).all()

    series = []
    total_tokens = 0
    calls = 0
    latency_sum = 0
    for model, day, tokens, call_count, lat_sum in rows:
        total_tokens += int(tokens or 0)
        calls += int(call_count or 0)
        latency_sum += int(lat_sum or 0)
        series.append(
            {
                "model": model,
                "date": day.isoformat(),
                "total_tokens": int(tokens or 0),
                "calls": int(call_count or 0),
                "avg_latency_ms": int(lat_sum or 0) // int(call_count or 1),
            }
        )

    return {
        "total_tokens": total_tokens,
        "calls": calls,
        "avg_latency_ms": latency_sum // calls if calls else 0,
        "series": series,
    }
