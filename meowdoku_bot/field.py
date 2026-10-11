from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import cv2
import numpy as np

from .config import BoardReadingSettings, CatDetectionSettings, Settings
from .domain import Cell, CellBox
from .logging_setup import get_logger

log = get_logger("field")


class BoardReadError(RuntimeError):
    """Не удалось прочитать поле"""


@dataclass(frozen=True)
class Board:

    size: int
    colors: tuple[tuple[str, ...], ...]
    cats: frozenset[tuple[int, int]]
    centers: tuple[tuple[float, float], ...]
    tap_points: tuple[tuple[float, float], ...]
    palette: tuple[tuple[int, int, int], ...]
    cell_w: int
    cell_h: int

    def cell(self, row: int, col: int) -> str:
        return self.colors[row][col]

    def tap_point(self, row: int, col: int) -> tuple[float, float]:
        return self.tap_points[row * self.size + col]

    def __str__(self) -> str:
        lines = [f"N = {self.size}, котов найдено: {len(self.cats)}", ""]
        lines.append("   " + " ".join(f"{letter:>2}" 
                     for letter in "ABCDEFGHIJKLMNOP"[: self.size]))
        
        for row in range(self.size):
            mark = ""
        
            if self.cats:
                mark = "   котики: " + ", ".join(f"({r},{c})" 
                        for r, c in sorted(self.cats) if r == row)

            lines.append(f"{row:>2} " + " ".join(f"{self.colors[row][c]:>2}" 
                         for c in range(self.size)) + mark)

        return "\n".join(lines)


def _cluster(values: list[float], gap: float) -> list[float]:
    clusters: list[list[float]] = [[values[0]]]

    for value in values[1:]:
        if value - clusters[-1][-1] < gap:
            clusters[-1].append(value)

        else:
            clusters.append([value])

    return [float(np.mean(cluster)) for cluster in clusters]


def _letter(index: int) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index]


class CellDetector:

    def __init__(self, settings: BoardReadingSettings) -> None:
        self.settings = settings

    def find_cell_boxes(self, image: np.ndarray) -> list[CellBox]:
        candidates = self._square_components(image)

        if not candidates:
            raise BoardReadError("Не найдено ни одной клетки")

        median_width = float(np.median([box.width for box in candidates]))
        median_height = float(np.median([box.height for box in candidates]))

        boxes = [
            box
            for box in candidates
            if (abs(box.width - median_width) < \
                self.settings.size_tolerance * median_width) and \
               (abs(box.height - median_height) < \
                self.settings.size_tolerance * median_height)
        ]

        if not boxes:
            raise BoardReadError("Не осталось клеток после отсева по размеру")

        log.debug(
            "квадратных компонент %d, после отсева по размеру %d, клетка %.0fx%.0f",
            len(candidates), len(boxes), median_width, median_height,
        )
        return boxes

    def build_grid(self, boxes: list[CellBox]) -> tuple[int, dict[Cell, CellBox]]:

        cell_height = float(np.median([box.height for box in boxes]))
        cell_width = float(np.median([box.width for box in boxes]))

        row_centers = _cluster(sorted(box.center_y for box in boxes), cell_height * 0.4)
        col_centers = _cluster(sorted(box.center_x for box in boxes), cell_width * 0.4)

        rows = len(row_centers)
        cols = len(col_centers)

        if rows != cols:
            raise BoardReadError(f"поле не квадратное: {rows} строк, {cols} столбцов")

        size = rows
        cells: dict[Cell, CellBox] = {}

        for box in boxes:

            cell = Cell(
                row=self._nearest(box.center_y, row_centers),
                col=self._nearest(box.center_x, col_centers),
            )

            if cell in cells:
                raise BoardReadError(f"две клетки попали в одну позицию {cell}")

            cells[cell] = box

        if len(cells) != size * size:
            missing = [cell for row in range(size) for col in range(size)
                       if (cell := Cell(row, col)) not in cells]

            if not self._grid_is_regular(row_centers, col_centers,
                                         cell_width, cell_height):

                raise BoardReadError(
                    f"найдено {len(cells)} клеток, а {size}x{size} = {size * size}, "
                    "и достроить не выходит: нерегулярная сетка"
                )

            width = round(cell_width)
            height = round(cell_height)

            for cell in missing:

                cells[cell] = CellBox(
                    left=round(col_centers[cell.col] - width / 2),
                    top=round(row_centers[cell.row] - height / 2),
                    width=width,
                    height=height,
                )

            log.debug(
                "достроили %d клеток: %s",
                len(missing), ", ".join(str(cell) for cell in missing),
            )

        return size, cells

    def _square_components(self, image: np.ndarray) -> list[CellBox]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        mask = (
            (hsv[:, :, 1].astype(np.int16) > self.settings.min_saturation)
            & (hsv[:, :, 2].astype(np.int16) > self.settings.min_value)
        ).astype(np.uint8)

        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

        found = []

        for index in range(1, count):
            left, top, width, height, area = stats[index]

            if area < self.settings.min_cell_area:
                continue

            if not self.settings.aspect_min < (width / height) < self.settings.aspect_max:
                continue

            found.append(CellBox(left=int(left), top=int(top), 
                                 width=int(width), height=int(height)))
        
        return found

    def _grid_is_regular(self, row_centers: list[float], 
                         col_centers: list[float], cell_width: float, 
                         cell_height: float) -> bool:

        for centers, cell in ((row_centers, cell_height), (col_centers, cell_width)):

            steps = [second - first for first, second in pairwise(centers, centers[1:])]

            if not steps:
                continue

            median = float(np.median(steps))

            if any(abs(step - median) > cell * self.settings.grid_step_tolerance 
                   for step in steps):
                return False

        return True

    @staticmethod
    def _nearest(value: float, centers: list[float]) -> int:
        return int(np.argmin([abs(value - center) for center in centers]))


class ColorReader:

    def __init__(self, settings: BoardReadingSettings) -> None:
        self.settings = settings

    def read_cell_colors(self, image: np.ndarray, cells: dict[Cell, CellBox]
                         ) -> dict[Cell, np.ndarray]:

        return {cell: self._mode_color(self._ring_pixels(image, box))
                for cell, box in cells.items()}

    def build_palette(self, cell_colors: dict[Cell, np.ndarray]) -> list[np.ndarray]:

        palette: list[np.ndarray] = []

        for cell in sorted(cell_colors):
            color = cell_colors[cell]

            if all(self._distance(existing, color) >= self.settings.palette_tolerance
                   for existing in palette):
                
                palette.append(color)
        
        return palette

    def assign_letters(self, size: int, cell_colors: dict[Cell, np.ndarray], 
                       palette: list[np.ndarray]) -> tuple[tuple[str, ...], ...]:

        # ЧЕ ЗА ХУЙНЯ АЛО ИИШНЫЙ КОД
        
        return tuple(
            tuple(
                _letter(
                    min(
                        range(len(palette)),
                        key=lambda index: self._distance(palette[index], 
                                                         cell_colors[Cell(row, col)]),
                    )
                )
                for col in range(size)
            )
            for row in range(size)
        )

    def _ring_pixels(self, image: np.ndarray, box: CellBox) -> np.ndarray:
        thickness = max(3, int(box.smaller_side * self.settings.ring_ratio))

        strips = [
            image[box.top : box.top + thickness, box.left : box.left + box.width],
            image[box.top + box.height - thickness : box.top + box.height, box.left : box.left + box.width],
            image[box.top : box.top + box.height, box.left : box.left + thickness],
            image[box.top : box.top + box.height, box.left + box.width - thickness : box.left + box.width],
        ]

        return np.concatenate([strip.reshape(-1, 3) for strip in strips])

    def _mode_color(self, pixels: np.ndarray) -> np.ndarray:
        quantized = pixels // self.settings.color_quantum * self.settings.color_quantum
        values, counts = np.unique(quantized, axis=0, return_counts=True)
        
        return values[int(np.argmax(counts))].astype(np.float32)

    @staticmethod
    def _distance(first: np.ndarray, second: np.ndarray) -> float:
        return float(np.abs(first - second).sum())


class CatDetector:
    
    def __init__(self, settings: CatDetectionSettings) -> None:
        self.settings = settings

    def find_cats(self, image: np.ndarray, cells: dict[Cell, CellBox], 
                  cell_colors: dict[Cell, np.ndarray]) -> frozenset[Cell]:
        
        found = {
            cell
            for cell, box in cells.items()
            if self._has_cat(image, box, cell_colors[cell])
        }
        
        if found:
            log.debug("котики: %s", ", ".join(str(cell) for cell in sorted(found)))
        
        return frozenset(found)

    def _has_cat(self, image: np.ndarray, box: CellBox, color: np.ndarray) -> bool:

        inner = self._inner_pixels(image, box)

        if inner.size == 0:
            return False

        deviation = np.abs(inner - color).sum(axis=1)

        if float((deviation > self.settings.deviation).mean()) <= self.settings.area_ratio:
            return False

        return float((inner.max(axis=1) < self.settings.dark_value).mean()) > \
                                                    self.settings.dark_ratio

    @staticmethod
    def _inner_pixels(image: np.ndarray, box: CellBox) -> np.ndarray:

        return image[
            box.top + int(box.height * 0.25) : box.top + int(box.height * 0.75),
            box.left + int(box.width * 0.25) : box.left + int(box.width * 0.75),
        ].reshape(-1, 3).astype(np.float32)


class BoardReader:

    def __init__(self, settings: Settings | None = None) -> None:
        resolved = settings or Settings()
        self.cells_detector = CellDetector(resolved.board)
        self.colors_reader = ColorReader(resolved.board)
        self.cats_detector = CatDetector(resolved.cat)

    def read(self, image: np.ndarray) -> Board:
        boxes = self.cells_detector.find_cell_boxes(image)
        size, cells = self.cells_detector.build_grid(boxes)

        cell_colors = self.colors_reader.read_cell_colors(image, cells)
        palette = self.colors_reader.build_palette(cell_colors)

        if len(palette) != size:
            raise BoardReadError(
                f"в палитре {len(palette)} цветов, а клеток в строке {size}. "
                "Цвета прочитаны неверно"
            )

        colors = self.colors_reader.assign_letters(size, cell_colors, palette)
        self._check_regions_contiguous(size, colors)

        cats = self.cats_detector.find_cats(image, cells, cell_colors)
        self._check_cats_count(size, cats)

        centers, tap_points, cell_width, cell_height = self._geometry(size, cells)

        return Board(
            size=size,
            colors=colors,
            cats=frozenset((cell.row, cell.col) for cell in cats),
            centers=centers,
            tap_points=tap_points,
            palette=tuple(tuple(int(value) for value in color) for color in palette),
            cell_w=cell_width,
            cell_h=cell_height,
        )

    def read_path(self, path: str) -> Board:
        image = cv2.imread(path)

        if image is None:
            raise BoardReadError(f"не удалось открыть скриншот {path}")

        return self.read(image)

    def _geometry(self, size: int, cells: dict[Cell, CellBox]
                  ) -> tuple[tuple, tuple, int, int]:

        cell_width = int(np.median([box.width for box in cells.values()]))
        cell_height = int(np.median([box.height for box in cells.values()]))

        centers = []
        tap_points = []

        for row in range(size):
            for col in range(size):
                box = cells[Cell(row, col)]
                centers.append((box.center_x, box.center_y))
                tap_points.append((box.center_x, box.center_y))

        return tuple(centers), tuple(tap_points), cell_width, cell_height

    @staticmethod
    def _check_cats_count(size: int, cats: frozenset[Cell]) -> None:
        if len(cats) > size:
            raise BoardReadError(
                f"нашлось {len(cats)} котиков на поле {size}x{size}, "
                f"а котиков ровно {size}. Это не игровое поле"
            )

    @staticmethod
    def _check_regions_contiguous(size: int, colors: Sequence[Sequence[str]]) -> None:
        """Цвета образовывают связные области"""
        
        for letter in sorted({color for row in colors for color in row}):
            
            cells = {
                Cell(row, col)
                for row in range(size)
                for col in range(size)
                if colors[row][col] == letter
            }
            
            seen: set[Cell] = set()
            parts = 0

            for start in sorted(cells):
            
                if start in seen:
                    continue
            
                parts += 1
                stack = [start]
                seen.add(start)
            
                while stack:
                    cell = stack.pop()
            
                    for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        neighbor = Cell(cell.row + step[0], cell.col + step[1])
            
                        if neighbor in cells and neighbor not in seen:
                            seen.add(neighbor)
                            stack.append(neighbor)

            if parts > 1:
                raise BoardReadError(
                    f"цвет {letter} распался на {parts} области, а должен быть один"
                )


def read_board(path: str) -> Board:
    return BoardReader().read_path(path)


def read_or_none(path: str) -> Board | None:
    try:
        return read_board(path)

    except BoardReadError:
        return None
