import pytest
import random
import uuid
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import Field, ValidationError
from sqlalchemy import Uuid, Column, String, DateTime, select, desc

from backend.core.db import Base
from backend.core.exception import ApiServerException
from backend.schema.query import PaginationQueryBasic, SortQueryBasic, FilterBasic
from test.conftest import generate_string


class TestModel(Base):
    __test__ = False
    __tablename__ = "test_table"
    id: UUID = Column(Uuid(as_uuid=True), primary_key=True)
    name: str = Column(String(255))
    created_at: datetime = Column(DateTime)


class TestModelQuery(PaginationQueryBasic, SortQueryBasic, FilterBasic):
    """
    쿼리를 검증하기 위한 테스트 스키마
    <URL example>
    /?page={page}&per_page={per_page}&sort_by=[created_at]&order_by=[asc/desc]
    &id=eq:7fe77ea8-0973-4adf-81af-9b50bf5b46f6
    &name=like:bada
    """
    __test__ = False
    sort_by: Optional[str] = Field(default=None, pattern=f'^(created_at)$')
    id: Optional[str] = Field(default=None, pattern=f'^(eq|in|not):.+', isFilter=True)
    name: Optional[str] = Field(default=None, pattern=f'^(eq|like):.+', isFilter=True)


def test_default_value():
    """
    optional parameter가 default value로 초기화되는지 확인
    (page, per_page는 1, 10으로 초기화되고, 나머지는 None)
    """
    defaultQueryInput = TestModelQuery()
    assert defaultQueryInput.page == 1
    assert defaultQueryInput.per_page == 10
    assert defaultQueryInput.sort_by is None
    assert defaultQueryInput.order_by is None
    assert defaultQueryInput.id is None
    assert defaultQueryInput.name is None


def test_pagination_basic():
    """
    pagination 잘 동작하는지 확인
    """
    page = random.randint(1, 10)
    per_page = random.randint(1, 100)
    queryInput = TestModelQuery(page=page, per_page=per_page)
    assert queryInput.page == page
    assert queryInput.per_page == per_page

    page = random.randint(1, 10)
    queryInput = TestModelQuery(page=page)
    assert queryInput.page == page
    assert queryInput.per_page == 10  # per_page's default value

    per_page = random.randint(1, 10)
    queryInput = TestModelQuery(per_page=per_page)
    assert queryInput.page == 1  # page's default value
    assert queryInput.per_page == per_page


def test_pagination_query_basic():
    """
    get_paginated_query에서 쿼리를 잘 반환하는지 확인
    """
    page = random.randint(1, 10)
    per_page = random.randint(1, 10)
    list_query = select(TestModel)

    actual_query = TestModelQuery(page=page, per_page=per_page).get_paginated_query(list_query)
    expected_query = list_query.offset((page - 1) * per_page).limit(per_page)

    assert str(expected_query) == str(actual_query)


def test_pagination_query_validation():
    """
    pagination 필드 제약 조건 불만족시 오류 발생하는지 확인
    자연수가 아닐 때 에러가 발생한다
    """
    with pytest.raises(ValidationError):
        # &page=-1
        TestModelQuery(page=-1)
    with pytest.raises(ValidationError):
        # &per_page=-1
        TestModelQuery(per_page=-1)
    with pytest.raises(ValidationError):
        # &page=one
        TestModelQuery(page="one")


def test_sort_basic():
    """
    sort schema 정상 동작 확인 
    """
    field_name = 'created_at'
    order_by = 'asc'
    queryInput = TestModelQuery(sort_by=field_name, order_by=order_by)
    assert queryInput.sort_by == field_name
    assert queryInput.order_by == order_by


def test_sort_validation():
    """
    sort 필드 제약 조건 불만족시 오류 발생하는지 확인
    """
    with pytest.raises(ValidationError):
        # &order_by=wrong_order
        TestModelQuery(order_by='wrong_order')
    with pytest.raises(ValidationError):
        # sort_by 만 있는 경우
        TestModelQuery(sort_by='asc')
    with pytest.raises(ValidationError):
        # &sort_by=wrong_field
        TestModelQuery(sort_by='wrong_field')

def test_sort_query_basic():
    """
    get sorted query에서 쿼리를 잘 반환하는지 확인
    """
    list_query = select(TestModel)
    # &sort_by=created_at&order_by=desc
    actual_query = TestModelQuery(sort_by='created_at', order_by='desc').get_sorted_query(list_query, TestModel)
    expected_query = select(TestModel).order_by(desc(TestModel.created_at))

    assert str(expected_query) == str(actual_query)

    list_query = select(TestModel)
    # &sort_by=created_at
    actual_query = TestModelQuery(sort_by='created_at').get_sorted_query(list_query, TestModel)
    expected_query = select(TestModel).order_by(TestModel.created_at)

    assert str(expected_query) == str(actual_query)


def test_filter_validation():
    """
    filter 필드 제약 조건 불만족시 오류 발생하는지 확인
    """
    with pytest.raises(ValidationError):
        # {op}:{value}의 형식이 아닌 경우
        TestModelQuery(id=f'smth')
    with pytest.raises(ValidationError):
        # {op}:{value}의 형식이 아닌 경우
        TestModelQuery(id=f'eq=1234')
    with pytest.raises(ValidationError):
        # 명시한 filter operator 아닌 경우
        TestModelQuery(id=f'wrong_op:1234')
    with pytest.raises(ValidationError):
        # 해당 필드의 조건이 아닌 경우
        TestModelQuery(name=f'not:1234')
    with pytest.raises(ApiServerException):
        # uuid 타입을 지키지 않은 경우
        TestModelQuery(id='eq:1234').get_filtered_query(select(TestModel), TestModel)


def test_filter_query_eq():
    """
    equal query를 잘 반환하는지 확인
    """
    id = uuid.uuid4()
    list_query = select(TestModel)
    # &id=eq:{uuid}
    actual_query = TestModelQuery(id=f'eq:{id}').get_filtered_query(list_query, TestModel)
    expected_query = list_query.filter(TestModel.id == id)

    assert str(expected_query) == str(actual_query)


def test_filter_query_not():
    """
    filter query를 잘 반환하는지 확인
    """
    id = uuid.uuid4()
    list_query = select(TestModel)
    # &id=not:{uuid}
    actual_query = TestModelQuery(id=f'not:{id}').get_filtered_query(list_query, TestModel)
    expected_query = list_query.filter(TestModel.id != id)

    assert str(expected_query) == str(actual_query)


def test_filter_query_in():
    """
    in query를 잘 반환하는지 확인
    """
    id_list = [uuid.uuid4() for _ in range(random.randint(1, 100))]
    id_list_str = ','.join([str(id) for id in id_list])
    list_query = select(TestModel)
    # &id=in:{uuid},{uuid},...
    actual_query = TestModelQuery(id=f'in:{id_list_str}').get_filtered_query(list_query, TestModel)
    expected_query = list_query.filter(TestModel.id.in_(id_list))

    assert str(expected_query) == str(actual_query)


def test_filter_query_like():
    """
    like query를 잘 반환하는지 확인
    """
    name_part = generate_string(10)
    list_query = select(TestModel)
    # &id=like:{name_part}
    actual_query = TestModelQuery(name=f'like:{name_part}').get_filtered_query(list_query, TestModel)
    expected_query = list_query.filter(TestModel.name.like(f'%{name_part}%'))

    assert str(expected_query) == str(actual_query)


def test_composite_query():
    """
    복합쿼리를 잘 파싱하는지를 확인
    <URL>
    get/
    ?page={page}
    &per_page={per_page}
    &sort_by=created_at
    &order_by=desc
    &id=eq:{id}
    &name=like:{name}
    """
    page = random.randint(1, 10)
    per_page = random.randint(1, 10)
    sort_by = 'created_at'
    order_by = 'desc'
    id = uuid.uuid4()
    id_eq = f'eq:{id}'
    name = generate_string(10)
    name_like = f'like:{name}'
    queryInput = TestModelQuery(page=page, per_page=per_page, sort_by=sort_by, order_by=order_by,
                                id=id_eq, name=name_like)
    list_query = select(TestModel)
    # 1. filter query
    actual_query = queryInput.get_filtered_query(list_query, TestModel)
    expected_query = list_query.filter(TestModel.id == id).filter(TestModel.name.like(f'%{name}%'))

    assert str(actual_query) == str(expected_query)
    # 2. sort query
    actual_query = queryInput.get_sorted_query(actual_query, TestModel)
    expected_query = expected_query.order_by(desc(TestModel.created_at))

    assert str(actual_query) == str(expected_query)
    # 3. pagination query
    actual_query = queryInput.get_paginated_query(actual_query)
    expected_query = expected_query.offset((page - 1) * per_page).limit(per_page)

    assert str(actual_query) == str(expected_query)
