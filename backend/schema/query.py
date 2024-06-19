from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional, Literal
from sqlalchemy import Column, Uuid
from sqlalchemy.sql import Select, desc
from fastapi import status

from backend.core.db import Base
from backend.core.exception import ApiServerException


class PaginationQueryBasic(BaseModel):
    """
    list api에서 Pagination을 위한 스키마

    :param page: 요청 페이지
    :param per_page: 페이지당 갯수
    """
    page: Optional[int] = Field(default=1, ge=1)
    per_page: Optional[int] = Field(default=10, ge=1)

    def get_paginated_query(self, query: Select) -> Select:
        strt_idx = (self.page - 1) * self.per_page
        return query.offset(strt_idx).limit(self.per_page)


class SortQueryBasic(BaseModel):
    """
    list api에서 정렬을 위한 스키마
    
    :param sort_by: 정렬 기준 필드
    :param order_by: 정렬 방향(오름차순, 내림차순)
    """
    sort_by: Optional[str] = Field(default=None, min_length=1)
    order_by: Optional[Literal['asc', 'desc']] = Field(default=None)

    def get_sorted_query(self, query: Select, db_model: Base) -> Select:
        if self.sort_by:
            if not hasattr(db_model, self.sort_by):
                # sort_by는 schema에서 field 이름으로 정의되야함
                raise ApiServerException(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            model_field = getattr(db_model, self.sort_by)
            query = query.order_by(desc(
                model_field)) if self.order_by == 'desc' else query.order_by(model_field)
        return query


class FilterBasic(BaseModel):
    def get_filtered_query(self, query: Select, db_model: Base) -> Select:
        for field_name, field_info in self.model_fields.items():
            if field_info.json_schema_extra and 'isFilter' in field_info.json_schema_extra:
                if hasattr(self, field_name) and getattr(self, field_name):
                    raw_filter_str: str = getattr(self, field_name)  # ex) like:2
                    op, value = raw_filter_str.split(':')
                    db_field: Column = getattr(db_model, field_name)
                    # 1. db_field가 uuid인 경우 (eq, not, in) => value를 uuid 타입으로 변환해야함
                    if isinstance(db_field.type, Uuid):
                        try:
                            if op == 'eq':
                                query = query.filter(db_field == UUID(value))
                            elif op == 'not':
                                query = query.filter(db_field != UUID(value))
                            elif op == 'in':
                                in_list = list(map(UUID, value.split(',')))
                                query = query.filter(db_field.in_(in_list))
                            else:
                                # eq, in, not, like로 구성되어 있어야함
                                raise ApiServerException(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        except ValueError:
                            # 올바르지 않은 uuid 입력시 400 에러 발생
                            raise ApiServerException(status=status.HTTP_400_BAD_REQUEST, message='Should be Valid UUID')
                    else:
                        if op == 'eq':
                            query = query.filter(db_field == value)
                        elif op == 'in':
                            # check value is valid list
                            in_list = value.split(',')
                            query = query.filter(db_field.in_(in_list))
                        elif op == 'not':
                            query = query.filter(db_field != value)
                        elif op == 'like':
                            query = query.filter(db_field.like(f'%{value}%'))
                        else:
                            # eq, in, not, like로 구성되어 있어야함
                            raise ApiServerException(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return query
