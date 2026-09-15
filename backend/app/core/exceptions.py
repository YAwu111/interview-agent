class AppError(Exception):
    """业务错误基类：全局异常处理归一为 {detail}。"""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
