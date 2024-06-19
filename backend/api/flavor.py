from typing import List
from fastapi import APIRouter, Depends, status

from backend.core.dependency import get_token_or_raise
from backend.schema.server import FlavorDto
from backend.service.flavor import FlavorService

router = APIRouter(prefix="/flavors", tags=["flavor"])


@router.get("/", response_model=List[FlavorDto], status_code=status.HTTP_200_OK)
async def get_flavors(token: str = Depends(get_token_or_raise), service: FlavorService = Depends()):
    """
    [API] - Get Flaovr List
    :param token: 인증토큰
    :return: 200 - flavor list
    :raises 401: 인증 오류
    """
    return await service.get_flavors(token)
