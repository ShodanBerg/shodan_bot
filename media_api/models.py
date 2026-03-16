from sqlalchemy import Column, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

gif_tag_association = Table(
    'gif_tag',
    Base.metadata,
    Column('gif_id', Integer, ForeignKey('gifs.id', ondelete="CASCADE"), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete="CASCADE"), primary_key=True)
)

class Gif(Base):
    __tablename__ = "gifs"

    id = Column(Integer, primary_key=True, index=True)
    telegram_file_id = Column(String, unique=True, index=True)
    file_path = Column(String, unique=True, nullable=False)

    tags = relationship("Tag", secondary=gif_tag_association, back_populates="gifs", lazy="selectin")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    # Обратная связь с гифками
    gifs = relationship("Gif", secondary=gif_tag_association, back_populates="tags")