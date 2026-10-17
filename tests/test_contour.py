"""Автоматические тесты чистых функций и работы с SQLite в памяти."""

from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from contour.core import contour_path, is_image, make_contour, scaled_size
from contour.database import (
    Conversion,
    count_conversions,
    create_database_engine,
    format_stat,
    save_conversion,
)
from contour.service import convert_one, get_formatted_stats, run_conversion


@pytest.fixture
def session() -> Session:
    """Создаёт изолированную базу SQLite в памяти для каждого теста."""
    engine = create_database_engine("sqlite:///:memory:")
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def test_contour_path_for_jpg() -> None:
    assert contour_path(Path("photos/a.jpg")) == Path("photos/a_contour.png")


def test_contour_path_for_png() -> None:
    assert contour_path(Path("a.png")) == Path("a_contour.png")


@pytest.mark.parametrize("name", ["a.jpg", "b.JPEG", "c.PNG", "x.JpG"])
def test_is_image_accepts_supported_extensions(name: str) -> None:
    assert is_image(Path(name)) is True


@pytest.mark.parametrize("name", ["a.gif", "a.txt", "photo", "folder.webp"])
def test_is_image_rejects_unsupported_extensions(name: str) -> None:
    assert is_image(Path(name)) is False


@pytest.mark.parametrize(
    ("width", "height", "compression", "expected"),
    [
        (40, 20, 1.0, (40, 20)),
        (40, 20, 2.0, (20, 10)),
        (40, 20, 4.0, (10, 5)),
        (1, 1, 4.0, (1, 1)),
        (2, 3, 4.0, (1, 1)),
    ],
)
def test_scaled_size(
    width: int,
    height: int,
    compression: float,
    expected: tuple[int, int],
) -> None:
    assert scaled_size(width, height, compression) == expected


def test_scaled_size_rejects_invalid_compression() -> None:
    with pytest.raises(ValueError):
        scaled_size(10, 10, 4.5)


def test_scaled_size_rejects_zero_dimension() -> None:
    with pytest.raises(ValueError):
        scaled_size(0, 10, 1.0)


def test_make_contour_in_memory() -> None:
    image = Image.new("RGB", (40, 20), "white")
    result = make_contour(image, 2.0)
    assert result.size == (20, 10)
    assert result.mode == "L"


def test_save_and_count_conversions(session: Session) -> None:
    save_conversion(session, ".JPG")
    save_conversion(session, "jpeg")
    save_conversion(session, "PNG")
    assert count_conversions(session) == {"jpg": 1, "jpeg": 1, "png": 1}


def test_save_conversion_rejects_unknown_extension(session: Session) -> None:
    with pytest.raises(ValueError, match="Неподдерживаемое расширение"):
        save_conversion(session, "gif")
    assert session.query(Conversion).count() == 0


@pytest.mark.parametrize(
    ("count", "total", "view", "expected"),
    [
        (3, 10, "abs", "3"),
        (3, 10, "rel", "30.0%"),
        (3, 10, None, "3 (30.0%)"),
        (0, 0, "rel", "0.0%"),
        (0, 0, None, "0 (0.0%)"),
    ],
)
def test_format_stat(count: int, total: int, view: str | None, expected: str) -> None:
    assert format_stat(count, total, view) == expected


def test_empty_stats(session: Session) -> None:
    total, formatted = get_formatted_stats(session, None)
    assert total == 0
    assert formatted == {
        "jpg": "0 (0.0%)",
        "jpeg": "0 (0.0%)",
        "png": "0 (0.0%)",
    }


def test_convert_one_records_successful_file(tmp_path: Path, session: Session) -> None:
    source_path = tmp_path / "source.JPG"
    Image.new("RGB", (40, 20), "white").save(source_path)
    output_path = convert_one(source_path, 2.0, session)
    assert output_path.name == "source_contour.png"
    assert output_path.is_file()
    assert Image.open(output_path).size == (20, 10)
    assert count_conversions(session)["jpg"] == 1


def test_run_conversion_directory_ignores_existing_outputs(
    tmp_path: Path, session: Session
) -> None:
    Image.new("RGB", (8, 8), "white").save(tmp_path / "photo.png")
    Image.new("RGB", (8, 8), "white").save(tmp_path / "old_contour.png")
    (tmp_path / "notes.txt").write_text("not an image", encoding="utf-8")
    result = run_conversion(tmp_path, 1.0, session)
    assert len(result.converted) == 1
    assert result.converted[0].name == "photo_contour.png"
    assert result.errors == []
    assert count_conversions(session)["png"] == 1


def test_run_conversion_reports_corrupted_image(
    tmp_path: Path, session: Session
) -> None:
    broken = tmp_path / "broken.jpg"
    broken.write_text("not really an image", encoding="utf-8")
    result = run_conversion(broken, 1.0, session)
    assert result.converted == []
    assert len(result.errors) == 1
    assert "Не удалось обработать" in result.errors[0][1]
    assert sum(count_conversions(session).values()) == 0
