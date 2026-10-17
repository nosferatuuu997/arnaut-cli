"""Командный интерфейс приложения на Click."""

import logging
from pathlib import Path

import click
from sqlalchemy.exc import SQLAlchemyError

from contour.database import create_database_engine, session_scope
from contour.service import get_formatted_stats, run_conversion


def configure_logging() -> None:
    """Настраивает запись логов в app.log без повторных обработчиков."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    target = str(Path("app.log").resolve())
    if not any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", None) == target
        for handler in root_logger.handlers
    ):
        handler = logging.FileHandler(target, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root_logger.addHandler(handler)


@click.group()
def cli() -> None:
    """Утилита для создания контуров изображений и просмотра статистики."""
    configure_logging()


@cli.command()
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True, path_type=Path),
)
@click.option(
    "--compression",
    "-c",
    type=click.FloatRange(1.0, 4.0),
    default=1.0,
    show_default=True,
    help="Во сколько раз уменьшить стороны изображения (от 1.0 до 4.0).",
)
def run(path: Path, compression: float) -> None:
    """Преобразует изображение или все изображения в папке PATH."""
    engine = None
    try:
        engine = create_database_engine()
        with session_scope(engine) as session:
            result = run_conversion(path, compression, session)
    except (OSError, SQLAlchemyError) as exc:
        message = f"Ошибка базы данных или файловой системы: {exc}"
        raise click.ClickException(message) from exc
    finally:
        if engine is not None:
            engine.dispose()

    for output in result.converted:
        click.echo(f"Готово: {output}")
    for source, message in result.errors:
        click.echo(f"Ошибка: {source}: {message}", err=True)

    if not result.converted and not result.errors:
        click.echo("В папке не найдено подходящих изображений.", err=True)
        raise click.ClickException("Нет изображений для обработки.")
    if result.errors:
        raise click.ClickException(
            "Успешно обработано: "
            f"{len(result.converted)}; ошибок: {len(result.errors)}."
        )
    click.echo(f"Успешно обработано изображений: {len(result.converted)}")


@cli.command()
@click.option(
    "--view",
    type=click.Choice(["abs", "rel"], case_sensitive=True),
    default=None,
    help="abs — абсолютные количества, rel — проценты; без опции — оба вида.",
)
def stats(view: str | None) -> None:
    """Показывает статистику успешно обработанных изображений."""
    engine = None
    try:
        engine = create_database_engine()
        with session_scope(engine) as session:
            total, formatted = get_formatted_stats(session, view)
    except SQLAlchemyError as exc:
        raise click.ClickException(f"Не удалось получить статистику: {exc}") from exc
    finally:
        if engine is not None:
            engine.dispose()

    click.echo(f"Всего конвертировано: {total}")
    for extension in ("jpg", "jpeg", "png"):
        click.echo(f"{extension}: {formatted[extension]}")
