"""Модели SQLAlchemy и функции работы с SQLite."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import DateTime, Engine, String, create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = "sqlite:///stats.db"
STAT_EXTENSIONS = ("jpg", "jpeg", "png")


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy."""


class Conversion(Base):
    """Одна успешно завершённая конвертация изображения."""

    __tablename__ = "conversions"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_extension: Mapped[str] = mapped_column(String(8), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def create_database_engine(database_url: str = DATABASE_URL) -> Engine:
    """Создаёт движок и необходимые таблицы."""
    options = {"check_same_thread": False} if database_url.startswith("sqlite:") else {}
    engine = create_engine(database_url, connect_args=options)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Открывает сессию и гарантирует её закрытие."""
    with Session(engine) as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def save_conversion(session: Session, extension: str) -> None:
    """Сохраняет факт успешной конвертации и фиксирует транзакцию."""
    normalized = extension.lower().lstrip(".")
    if normalized not in STAT_EXTENSIONS:
        raise ValueError(f"Неподдерживаемое расширение: {extension}")
    try:
        session.add(Conversion(source_extension=normalized))
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise


def count_conversions(session: Session) -> dict[str, int]:
    """Считает конвертации по расширениям непосредственно в SQL."""
    statement = select(Conversion.source_extension, func.count()).group_by(
        Conversion.source_extension
    )
    rows = session.execute(statement).all()
    counts = {extension: 0 for extension in STAT_EXTENSIONS}
    for extension, count in rows:
        if extension in counts:
            counts[extension] = count
    return counts


def format_stat(count: int, total: int, view: str | None) -> str:
    """Форматирует количество, процент или оба значения."""
    percent = count / total * 100 if total else 0.0
    if view == "abs":
        return str(count)
    if view == "rel":
        return f"{percent:.1f}%"
    return f"{count} ({percent:.1f}%)"
