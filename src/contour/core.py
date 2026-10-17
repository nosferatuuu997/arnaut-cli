"""Чистые функции для обработки путей и изображений."""

from pathlib import Path

from PIL import Image, ImageFilter

SUPPORTED_EXTENSIONS = ("jpg", "jpeg", "png")


def is_image(path: Path | str) -> bool:
    """Возвращает True, если расширение файла поддерживается."""
    return Path(path).suffix.lower().lstrip(".") in SUPPORTED_EXTENSIONS


def contour_path(path: Path | str) -> Path:
    """Создаёт путь для PNG-файла с контурами рядом с оригиналом."""
    source = Path(path)
    return source.with_name(f"{source.stem}_contour.png")


def scaled_size(width: int, height: int, compression: float = 1.0) -> tuple[int, int]:
    """Рассчитывает размер изображения после уменьшения."""
    if width < 1 or height < 1:
        raise ValueError("Ширина и высота должны быть положительными числами.")
    if not 1.0 <= compression <= 4.0:
        raise ValueError("Сжатие должно находиться в диапазоне от 1.0 до 4.0.")
    return max(1, int(width / compression)), max(1, int(height / compression))


def make_contour(image: Image.Image, compression: float = 1.0) -> Image.Image:
    """Возвращает чёрно-белый контур изображения в памяти."""
    size = scaled_size(image.width, image.height, compression)
    grayscale = image.convert("L")
    edges = grayscale.filter(ImageFilter.CONTOUR)
    if edges.size != size:
        edges = edges.resize(size)
    return edges
