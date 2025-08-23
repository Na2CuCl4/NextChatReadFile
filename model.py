from pydantic import BaseModel
from starlette.responses import JSONResponse


class BaseResponse(JSONResponse):
    def __init__(self, code: int = 0, msg: str = "", data=None, status_code: int = 200):
        if data is None:
            super().__init__(
                content=dict(code=code, msg=msg),
                status_code=status_code
            )
        else:
            super().__init__(
                content=dict(code=code, msg=msg, data=data),
                status_code=status_code
            )


class FilePayload(BaseModel):
    http_url: str = None
