from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import crud.crud_tags as crud_tags
import schemas.tag_schemas as tag_schemas
from database import get_db

router = APIRouter()

@router.post("/", response_model=tag_schemas.TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(tag: tag_schemas.TagCreate, db: Session = Depends(get_db)):
    """Создать новый тег (передается только имя)."""
    return crud_tags.create_tag(db=db, tag=tag)

@router.get("/", response_model=List[tag_schemas.TagResponse])
def get_all_tags(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получить список всех тегов."""
    return crud_tags.get_tags(db, skip=skip, limit=limit)

@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Удалить тег по его ID."""
    if not crud_tags.delete_tag(db=db, tag_id=tag_id):
        raise HTTPException(status_code=404, detail="Тег не найден")
    return None