from fastapi.exceptions import RequestValidationError

from test.conftest import generate_string
from backend.core.exception import OpenstackClientException
from backend.core.exception_handler import ExceptionParser, ErrorContent
from backend.schema.oa_base import OpenstackBaseResponse


# 발생할 수 있는 에러 파싱을 잘 수행하는지 확인한다
def test_oa_error():
    """
    openstack api에서 발생할 수 있는 오류를
    type, message, detail로 파싱하여 리턴하는지를 확인
    """
    error_type = generate_string(10)
    error_message = generate_string(10)
    error_detail = generate_string(10)
    error_data = {
        error_type: {
            "code": 409,
            "error_type": generate_string(10),
            "message": error_message,
            "detail": error_detail
        }
    }
    response = OpenstackBaseResponse(status=401, data=error_data)
    oa_exception = OpenstackClientException(response)

    result = ExceptionParser.parse_openstack_client_exception(oa_exception)
    expected = ErrorContent(error_type=error_type, message=error_message, detail=error_detail).__dict__
    assert expected == result


def test_pydantic_error():
    """
    pydantic request validation에서 발생할 수 있는 오류를
    type, message, detail로 파싱하여 리턴하는지를 확인
    """
    error_type = generate_string(10)
    error_message = generate_string(10)
    error_loc = [generate_string(5), generate_string(5)]
    error_input = generate_string(10)

    error_data = {
        'type': error_type,
        'loc': error_loc,
        'msg': error_message,
        'input': error_input,
        'url': 'https://errors.pydantic.dev/2.6/v/missing'
    }
    pydantic_exception = RequestValidationError((error_data,))

    result = ExceptionParser.parse_pydantic_exception(pydantic_exception)
    expected = ErrorContent(error_type=error_type, message=error_message,
                            detail={'input': error_input, 'loc': error_loc}).__dict__
    assert expected == result
