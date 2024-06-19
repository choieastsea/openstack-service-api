import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.core.exception import OpenstackClientException, ApiServerException

logger = logging.getLogger(__name__)


async def log_error(request: Request, exc: Exception):
    logger.error(exc.__class__.__name__)
    logger.error(
        f'{request.client.host}:{request.client.port} - "{request.method} {request.url}", {await request.body()}, {request.headers}')
    logger.error(exc)


def register_error_handlers(app: FastAPI):
    """
    exception 발생시, 이를 JSONResponse로 처리하여 리턴해주는 handler
    해당 함수 내부에서 에러 발생시 '500 Internal Server Error' 리턴
    """

    @app.exception_handler(RequestValidationError)
    async def request_exception_handler(request: Request, exc: RequestValidationError):
        # pydantic의 validation error 발생시 400 에러 발생시킨다
        await log_error(request, exc)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ExceptionParser.parse_pydantic_exception(exc))

    @app.exception_handler(OpenstackClientException)
    async def openstack_client_exception_handler(request: Request, exc: OpenstackClientException):
        await log_error(request, exc)
        # openstack client의 응답에 따라 end user에게 적절한 응답을 준다
        if exc.status == 400:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            status_code = exc.status
        return JSONResponse(status_code=status_code, content=ExceptionParser.parse_openstack_client_exception(exc))

    @app.exception_handler(ApiServerException)
    async def api_server_exception_handler(request: Request, exc: ApiServerException):
        await log_error(request, exc)
        return JSONResponse(status_code=exc.status, content=ExceptionParser.parse_api_server_exception(exc))


class ExceptionParser:
    """
    발생할 수 있는 내부 오류를 파싱하여 형식에 맞게 내보낸다
    {
        title : str,
        message : str,
        detail  : str
    }
    """

    @staticmethod
    def parse_openstack_client_exception(exc: OpenstackClientException):
        detail = exc.detail
        errors = []
        for key, value in detail.items():
            errors.append(
                ErrorContent(key, value['message'], value['detail'] if 'detail' in value else '').__dict__)
        return errors[0] if len(errors) == 1 else errors

    @staticmethod
    def parse_pydantic_exception(exc: RequestValidationError):
        errors = []
        for error in exc.errors():
            errors.append(ErrorContent(error['type'], error['msg'], {
                'input': error['input'], 'loc': error['loc']}).__dict__)
        return errors[0] if len(errors) == 1 else errors

    @staticmethod
    def parse_api_server_exception(exc: ApiServerException):
        return ErrorContent(error_type=exc.error_type, message=exc.message, detail=exc.detail).__dict__


class ErrorContent:
    def __init__(self, error_type: str, message: str, detail: Any) -> None:
        self.error_type = error_type
        self.message = message
        self.detail = detail
