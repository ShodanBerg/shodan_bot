from sqlalchemy.orm import Session
import models
import schemas.gif_schemas as gif_schemas


def create_gif(db: Session, gif: gif_schemas.GifCreate):
    existing_gif = db.query(models.Gif).filter(models.Gif.telegram_file_id == gif.telegram_file_id).first()
    if existing_gif:
        return existing_gif

    db_gif = models.Gif(telegram_file_id=gif.telegram_file_id, file_path=gif.file_path)

    if gif.tag_ids:
        tags = db.query(models.Tag).filter(models.Tag.id.in_(gif.tag_ids)).all()
        db_gif.tags.extend(tags)

    db.add(db_gif)
    db.commit()
    db.refresh(db_gif)
    return db_gif


def get_gifs(db: Session, tag_ids: list[int] = None, skip: int = 0, limit: int = 100, match_all: bool = False):
    query = db.query(models.Gif)

    if tag_ids:
        if match_all:
            for tag_id in tag_ids:
                query = query.filter(models.Gif.tags.any(models.Tag.id == tag_id))
        else:
            query = query.join(models.Gif.tags).filter(models.Tag.id.in_(tag_ids)).distinct()

    return query.offset(skip).limit(limit).all()


def delete_gif(db: Session, gif_id: int):
    db_gif = db.query(models.Gif).filter(models.Gif.id == gif_id).first()
    if db_gif:
        db.delete(db_gif)
        db.commit()
        return True
    return False