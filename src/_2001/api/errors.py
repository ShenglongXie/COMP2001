from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from _2001.core.logging import get_request_id

_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    503: "service_unavailable",
}


class ApiError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.message = message


def _body(code: str, message: str) -> dict[str, object]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(),
        }
    }


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_body(exc.code, exc.message),
        headers=getattr(exc, "headers", None),
    )


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = _CODE_BY_STATUS.get(exc.status_code, "http_error")
    return JSONResponse(
        status_code=exc.status_code,
        content=_body(code, str(exc.detail)),
        headers=getattr(exc, "headers", None),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {
            "location": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    body = _body("validation_error", "Request validation failed.")
    body["error"]["details"] = errors
    return JSONResponse(status_code=422, content=body)


def not_found(resource: str, identifier: object) -> ApiError:
    return ApiError(404, "not_found", f"{resource} {identifier} does not exist.")


def conflict(message: str) -> ApiError:
    return ApiError(409, "conflict", message)


def unprocessable(code: str, message: str) -> ApiError:
    return ApiError(422, code, message)
