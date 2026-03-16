from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import crud.crud_gifs as crud_gifs
import schemas.gif_schemas as gif_schemas
from database import get_db

router = APIRouter()

@router.post("/", response_model=gif_schemas.GifResponse, status_code=status.HTTP_201_CREATED)
def create_gif(gif: gif_schemas.GifCreate, db: Session = Depends(get_db)):
    """Создать гифку и привязать к ней теги по их ID."""
    return crud_gifs.create_gif(db=db, gif=gif)

@router.get("/any", response_model=List[gif_schemas.GifResponse], summary="Поиск: ХОТЯ БЫ ОДИН тег (ИЛИ)")
def get_gifs_any(
    tag_ids: List[int] = Query(None, description="Список ID тегов. Вернутся гифки, имеющие хотя бы один из них."),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    **Логика ИЛИ (OR):** Возвращает гифки, у которых есть совпадение хотя бы по одному переданному ID тега.
    Пример: `?tag_ids=1&tag_ids=2` вернет гифки, где есть тег 1, тег 2, или оба сразу.
    """
    return crud_gifs.get_gifs(db, tag_ids=tag_ids, skip=skip, limit=limit, match_all=False)

@router.get("/all", response_model=List[gif_schemas.GifResponse], summary="Поиск: ВСЕ теги строго (И)")
def get_gifs_all(
    tag_ids: List[int] = Query(None, description="Список ID тегов. Вернутся гифки, имеющие ВСЕ эти теги одновременно."),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    **Логика И (AND):** Возвращает гифки, у которых строго присутствуют все переданные ID тегов.
    Пример: `?tag_ids=1&tag_ids=2` вернет только те гифки, к которым привязаны и тег 1, и тег 2 одновременно.
    """
    return crud_gifs.get_gifs(db, tag_ids=tag_ids, skip=skip, limit=limit, match_all=True)

@router.delete("/{gif_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gif(gif_id: int, db: Session = Depends(get_db)):
    """Удалить гифку по её ID."""
    if not crud_gifs.delete_gif(db=db, gif_id=gif_id):
        raise HTTPException(status_code=404, detail="Гифка не найдена")
    return None