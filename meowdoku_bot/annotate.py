from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from .domain import Cell
from .field import Board
from .logging_setup import get_logger

log = get_logger("annotate")

COLOR_FOUND = (80, 80, 220)
COLOR_PLANNED = (80, 200, 80)
COLOR_GRID = (220, 220, 220)
COLOR_TEXT = (255, 255, 255)


class Annotator:

    def __init__(self) -> None:
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def render(self, source: str | Path, board: Board,
        destination: str | Path, planned: Sequence[Cell] = ()) -> Path:

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
                    img=result,
                    pt1=(int(center_x - half), int(center_y - half)),
                    pt2=(int(center_x + half), int(center_y + half)),
                    color=color,
                    thickness=thickness,
                )

                self._put(image=result, 
                          text=board.colors[row][col],
                          center=(center_x, center_y), 
                          offset=(0, cell_size * 0.14),
                          color=COLOR_TEXT, 
                          font_scale=font_scale, 
                          thickness=thickness
                )

                self._put(image=result, 
                          text=f"{row},{col}",
                          center=(center_x, center_y), 
                          offset=(-cell_size * 0.3, -cell_size * 0.24),
                          color=color, 
                          font_scale=font_scale * 0.8, 
                          thickness=thickness
                )

        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(destination), result)
        log.debug("Разбор сохранён: %s", destination)
        return Path(destination)

    def _put(self, image: np.ndarray, text: str, center: tuple[float, float],
             offset: tuple[float, float], color: tuple[int, int, int],
             font_scale: float, thickness: int) -> None:
        
        cv2.putText(
            image=      image,
            text=       text,
            org=        (int(center[0] + offset[0]), 
                         int(center[1] + offset[1])),
            fontFace=   self.font,
            fontScale=  font_scale,
            color=      color,
            thickness=  thickness,
            lineType=   cv2.LINE_AA,
        )

    @staticmethod
    def _cell_size(board: Board) -> float:
        if board.size < 2:
            return float(min(board.cell_w, board.cell_h))

        return float(board.centers[1][0] - board.centers[0][0])


def annotate(source: str | Path, board: Board, destination: str | Path,
             planned: Sequence[Cell] = ()) -> Path:

    return Annotator().render(source, board, destination, planned)


def show(source: str | Path, window: str = "board") -> None:

    image = cv2.imread(str(source))

    if image is None:
        raise FileNotFoundError(f"не удалось открыть {source}")

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, 800, 1200)
    cv2.imshow(window, image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
