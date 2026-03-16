from pydantic import BaseModel, ConfigDict
from schemas.tag_schemas import TagResponse

class GifBase(BaseModel):
    telegram_file_id: str
    file_path: str

class GifCreate(GifBase):
    tag_ids: list[int] = []

class GifResponse(GifBase):
    id: int
    tags: list[TagResponse] = []
    model_config = ConfigDict(from_attributes=True)