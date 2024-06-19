from backend.schema.oa_base import OpenstackBaseResponse
from typing import Optional


class OpenstackClientException(Exception):
    """
    openstack api를 호출하고 응답하면서 예외 경우에 발생하는 exception
    형식 참고 : https://specs.openstack.org/openstack/api-wg/guidelines/errors.html
    """

    def __init__(self, response: OpenstackBaseResponse):
        self.status = response.status
        self.detail = response.data
        self.headers = response.headers

    def __str__(self) -> str:
        return f'{self.detail}'


class ApiServerException(Exception):
    def __init__(
            self,
            status: int,
            error_type: Optional[str] = 'error',
            message: Optional[str] = '',
            detail: Optional[str] = '',
    ) -> None:
        self.error_type = error_type
        self.status = status
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        return f'{self.detail}'
