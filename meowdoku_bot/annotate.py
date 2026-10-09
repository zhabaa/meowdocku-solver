"""Отрисовка разбора поля поверх скриншота.

Нужна, чтобы глазами проверить, что бот собирается тапать: красным
обведены найденные котики, зелёным — клетки, куда пойдёт тап.
"""

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .domain import Cell
from .field import Board
from .logging_setup import get_logger

log = get_logger("annotate")

# Цвета рамок в BGR.
COLOR_FOUND = (80, 80, 220)
COLOR_PLANNED = (80, 200, 80)
COLOR_GRID = (220, 220, 220)
COLOR_TEXT = (255, 255, 255)


class Annotator:
    """Рисует поле поверх снимка экрана."""

    def __init__(self) -> None:
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def render(
        self,
        source: str | Path,
        board: Board,
        destination: str | Path,
        planned: Sequence[Cell] = (),
    ) -> Path:
        """Разбор поля в отдельный файл, исходный снимок не трогаем."""
        image = cv2.imread(str(source))
        if image is None:
            raise FileNotFoundError(f"не удалось открыть {source}")

        result = image.copy()
        cell_size = self._cell_size(board)
        thickness = max(1, int(cell_size * 0.04))
        font_scale = max(0.4, cell_size * 0.004)
        planned_cells = set(planned)

        for row in range(board.size):
            for col in range(board.size):
                cell = Cell(row, col)
                center_x, center_y = board.centers[row * board.size + col]
                half = cell_size * 0.42

                if (row, col) in board.cats:
                    color = COLOR_FOUND
                elif cell in planned_cells:
                    color = COLOR_PLANNED
                else:
                    color = COLOR_GRID

                cv2.rectangle(
                    result,
                    (int(center_x - half), int(center_y - half)),
                    (int(center_x + half), int(center_y + half)),
                    color,
                    thickness,
                )

                self._put(result, board.colors[row][col],
                          (center_x, center_y), (0, cell_size * 0.14),
                          COLOR_TEXT, font_scale, thickness)

                self._put(result, f"{row},{col}",
                          (center_x, center_y), (-cell_size * 0.3, -cell_size * 0.24),
                          color, font_scale * 0.8, thickness)

        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(destination), result)
        log.debug("разбор сохранён: %s", destination)
        return Path(destination)

    def _put(
        self,
        image: np.ndarray,
        text: str,
        center: tuple[float, float],
        offset: tuple[float, float],
        color: tuple[int, int, int],
        font_scale: float,
        thickness: int,
    ) -> None:
        cv2.putText(
            image,
            text,
            (int(center[0] + offset[0]), int(center[1] + offset[1])),
            self.font,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

    @staticmethod
    def _cell_size(board: Board) -> float:
        """Шаг сетки: расстояние между центрами соседних клеток."""
        if board.size < 2:
            return float(min(board.cell_w, board.cell_h))
        return float(board.centers[1][0] - board.centers[0][0])


def annotate(
    source: str | Path,
    board: Board,
    destination: str | Path,
    planned: Sequence[Cell] = (),
) -> Path:
    """Нарисовать разбор — короткий вызов для скриптов и тестов."""
    return Annotator().render(source, board, destination, planned)


def show(source: str | Path, window: str = "board") -> None:
    """Показать снимок в окне. Только для отладки, требует GUI."""
    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(f"не удалось открыть {source}")

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 800, 1200)
    cv2.imshow(window, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
