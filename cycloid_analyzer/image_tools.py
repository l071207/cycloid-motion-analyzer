from __future__ import annotations

from pathlib import Path

from PyQt5.QtGui import QImageReader, QPixmap


def load_png_pixmap(file_path: str) -> QPixmap:
    path = Path(file_path)
    if path.suffix.lower() != ".png":
        raise ValueError("Only PNG images are supported.")

    reader = QImageReader(str(path))
    if reader.format().data().decode("ascii", errors="ignore").lower() != "png":
        raise ValueError("The selected file is not a valid PNG image.")

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        raise ValueError("The PNG image could not be loaded.")
    return pixmap

