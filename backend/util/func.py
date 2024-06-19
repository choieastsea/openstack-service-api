from pydantic import BaseModel

from backend.core.db import Base


def update_model_value(db_model: Base, updateDto: BaseModel) -> None:
    for field, value in dict(updateDto).items():
        if hasattr(db_model, field) and value is not None:  # enable partial update
            setattr(db_model, field, value)
