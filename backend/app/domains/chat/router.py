"""对话领域路由。鉴权由 gateway 聚合注入；user_id 从 request.state 读取。"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.exceptions import AppError

from .schemas import MessageOut, SessionCreate, SessionOut, SessionUpdate, StreamRequest
from .service import get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


async def _owned_session(request: Request, session_id: str, svc):
    sess = await svc.get_session(request.state.user_id, session_id)
    if sess is None:
        raise AppError("会话不存在", status_code=404)
    return sess


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(request: Request, svc=Depends(get_chat_service)):
    return await svc.list_sessions(request.state.user_id)


@router.post("/sessions", response_model=SessionOut)
async def create_session(body: SessionCreate, request: Request, svc=Depends(get_chat_service)):
    return await svc.create_session(request.state.user_id, body.mode)


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str, body: SessionUpdate, request: Request, svc=Depends(get_chat_service)
):
    await _owned_session(request, session_id, svc)
    if body.mode is not None:
        await svc.update_session(request.state.user_id, session_id, body.mode)
    return {"ok": True}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request, svc=Depends(get_chat_service)):
    await _owned_session(request, session_id, svc)
    await svc.delete_session(request.state.user_id, session_id)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: str, request: Request, svc=Depends(get_chat_service)):
    await _owned_session(request, session_id, svc)
    return await svc.get_messages(request.state.user_id, session_id)


@router.post("/sessions/{session_id}/stream")
async def stream(
    session_id: str, body: StreamRequest, request: Request, svc=Depends(get_chat_service)
):
    sess = await _owned_session(request, session_id, svc)
    if sess.mode == "interview" and not svc.has_runner():
        raise AppError("面试服务未就绪", status_code=503)

    async def events():
        async for ev in svc.stream(sess, body.text):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/messages/{message_id}/stream")
async def resume_stream(
    session_id: str,
    message_id: str,
    request: Request,
    svc=Depends(get_chat_service),
):
    sess = await _owned_session(request, session_id, svc)
    raw = request.headers.get("last-event-id", "0")
    try:
        last_event_id = int(raw)
    except ValueError:
        last_event_id = 0

    async def events():
        async for ev in svc.resume(sess, message_id, last_event_id):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/stop")
async def stop(session_id: str, request: Request, svc=Depends(get_chat_service)):
    await _owned_session(request, session_id, svc)
    await svc.stop_stream(session_id)
    return {"ok": True}


@router.post("/sessions/{session_id}/end")
async def end(session_id: str, request: Request, svc=Depends(get_chat_service)):
    sess = await _owned_session(request, session_id, svc)
    if not svc.has_runner():
        raise AppError("面试服务未就绪", status_code=503)

    async def events():
        async for ev in svc.end_interview(sess):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
