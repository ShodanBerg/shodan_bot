import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import engine
import models
from routers import gifs_router, tags_router


models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GIF Organizer API",
    description="API для управления сохраненными Telegram-гифками с помощью тегов.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gifs_router.router, prefix="/api/gifs", tags=["Gifs"])
app.include_router(tags_router.router, prefix="/api/tags", tags=["Tags"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
media_path = os.path.join(BASE_DIR, "media")
gifs_path = os.path.join(media_path, "gifs")

os.makedirs(gifs_path, exist_ok=True)

app.mount("/media", StaticFiles(directory=media_path), name="media")