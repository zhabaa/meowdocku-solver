"""Отрисовка разбора поля поверх скриншота.

Нужна, чтобы глазами проверить, что бот собирается тапать.
"""

from pathlib import Path
from typing import Optional, Sequence

import cv2
import numpy as np

from field import Board

# Цвета рамок в BGR.
COLOR_FOUND = (80, 80, 220)
COLOR_PLANNED = (80, 200, 80)
COLOR_GRID = (220, 220, 220)


def annotate(
    source: str | Path,
    board: Board,
    destination: str | Path,
    planned: Sequence[tuple[int, int]] = (),
) -> Path:
    """Нарисовать поверх скриншота сетку, буквы цветов и котиков.

    Найденные котики обводятся красным, клетки, куда собираемся тапать, —
    зелёным. Остальное — просто рамки.
    """
    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(f"Не удалось открыть {source}")

    result = image.copy()
    unit = float(
        np.median(
            [
                abs(board.centers[i + 1][0] - board.centers[i][0])
                for i in range(board.n - 1)
            ]
        )
    )
    thickness = max(1, int(unit * 0.04))
    font_scale = max(0.4, unit * 0.004)

    for row in range(board.n):
        for col in range(board.n):
            cx, cy = board.centers[row * board.n + col]
            half = unit * 0.42

            color = COLOR_GRID
            if (row, col) in board.cats:
                color = COLOR_FOUND
            elif (row, col) in planned:
                color = COLOR_PLANNED

            cv2.rectangle(
                result,
                (int(cx - half), int(cy - half)),
                (int(cx + half), int(cy + half)),
                color,
                thickness,
            )

            letter = board.colors[row][col]
            cv2.putText(
                result,
                letter,
                (int(cx - unit * 0.14), int(cy + unit * 0.14)),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                thickness,
                cv2.LINE_AA,
            )

            cv2.putText(
                result,
                f"{row},{col}",
                (int(cx - unit * 0.3), int(cy - unit * 0.24)),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale * 0.8,
                color,
                thickness,
                cv2.LINE_AA,
            )

    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(destination), result)
    return Path(destination)


def show(source: str | Path, window: str = "board") -> None:
    """Показать скриншот в окне. Только для отладки, требует GUI."""
    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(f"Не удалось открыть {source}")

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 800, 1200)
    cv2.imshow(window, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()