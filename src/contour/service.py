"""Сценарии работы приложения, независимые от Click."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contour.core import contour_path, is_image, make_contour
from contour.database import count_conversions, format_stat, save_conversion

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Итоги запуска команды run."""

    converted: list[Path] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)
    skipped: int = 0


def convert_one(path: Path, compression: float, session: Session) -> Path:
    """Конвертирует один файл и сохраняет статистику после успеха."""
    if not path.is_file():
        raise ValueError(f"Это не файл: {path}")
    if not is_image(path):
        raise ValueError(f"Неподдерживаемый формат файла: {path.name}")

    output = contour_path(path)
    try:
        with Image.open(path) as source:
            result = make_contour(source.copy(), compression)
        result.save(output, format="PNG")
        save_conversion(session, path.suffix.lower().lstrip("."))
    except (OSError, SQLAlchemyError, ValueError) as exc:
        logger.exception("Не удалось обработать изображение %s", path)
        raise RuntimeError(f"Не удалось обработать {path.name}: {exc}") from exc

    logger.info("Успешно обработано %s -> %s", path, output)
    return output


def run_conversion(path: Path, compression: float, session: Session) -> RunResult:
    """Обрабатывает файл или все подходящие файлы в указанной папке."""
    result = RunResult()
    if path.is_file():
        try:
            result.converted.append(convert_one(path, compression, session))
        except (ValueError, RuntimeError) as exc:
            result.errors.append((path, str(exc)))
        return result

    if not path.is_dir():
        result.errors.append((path, f"Путь не является файлом или папкой: {path}"))
        return result

    sources = sorted(
        item
        for item in path.iterdir()
        if item.is_file()
        and is_image(item)
        and not item.stem.lower().endswith("_contour")
    )
    result.skipped = sum(
        1 for item in path.iterdir() if item.is_file() and not is_image(item)
    )
    for source in sources:
        try:
            result.converted.append(convert_one(source, compression, session))
        except (ValueError, RuntimeError) as exc:
            result.errors.append((source, str(exc)))
    if not sources:
        logger.info("В папке %s не найдено поддерживаемых изображений", path)
    return result


def get_formatted_stats(
    session: Session, view: str | None
) -> tuple[int, dict[str, str]]:
    """Возвращает общее число конвертаций и форматированную статистику."""
    counts = count_conversions(session)
    total = sum(counts.values())
    formatted = {
        extension: format_stat(count, total, view)
        for extension, count in counts.items()
    }
    return total, formatted
