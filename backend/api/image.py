from typing import List

from fastapi import APIRouter, Depends, status

from backend.core.dependency import get_token_or_raise
from backend.schema.server import ImageDto
from backend.service.image import ImageService

router = APIRouter(prefix="/images", tags=["image"])


@router.get("/", response_model=List[ImageDto], status_code=status.HTTP_200_OK)
async def get_images(token: str = Depends(get_token_or_raise), service: ImageService = Depends()):
    """
    [API] - Get Image List
    :param token: 인증토큰
    :return: 200 - image list
    :raises 401: 인증 오류
    """
    return await service.get_images(token)
