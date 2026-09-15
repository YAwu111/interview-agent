from fastapi import Request


def get_request_id(request: Request) -> str:
    """由 RequestIDMiddleware 写入 scope 的请求 ID。"""
    return request.scope.get("request_id", "")
