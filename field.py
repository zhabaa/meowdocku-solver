"""Чтение игрового поля Meowdoku со скриншота.

Поле — сетка N*N цветных квадратов. Правила игры:
  1 кошка на цвет, 1 кошка на строку, 1 кошка на столбец,
  кошки не касаются (даже по диагонали).

Начало координат — левый верхний угол поля, как в игре и как в adb input tap.
"""

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# Маска клеток: клетки насыщенные, фон и рамки бледные.
MIN_SATURATION = 40
MIN_VALUE = 60

# Отсев компонент: минимальная площадь и допуск по пропорциям сторон.
MIN_CELL_AREA = 500
ASPECT_LO = 0.75
ASPECT_HI = 1.33
# Допуск по размеру клетки. Внутри одного поля клетки отличаются на пиксель,
# а посторонние квадратики — на десятки: иконки котиков в шапке, блики вокруг
# счёта очков, кнопки внизу. При 0.3 проходил лишний квадрат 70x70 рядом с
# клетками 94x95, и поле читалось как 11 строк вместо 10.
SIZE_TOLERANCE = 0.15

# Точка тапа — центр клетки. Раньше тут было смещение (-2.6%, -5.1%),
# но перемер на семи котиках с четырёх скринов показало: кот рисуется по
# центру клетки, отклонение меньше пикселя. Прежнее смещение измерялось по
# маске, захватившей бордюр клетки, и было ошибкой.
TAP_OFFSET_X = 0.0
TAP_OFFSET_Y = 0.0

# Квантование цвета при поиске моды, чтобы шум не плодил ложные цвета.
COLOR_QUANTUM = 8
# Ширина кольца для замера цвета, доля от размера клетки.
RING_RATIO = 0.10
# Порог разницы цветов при кластеризации палитры.
PALETTE_TOLERANCE = 50
# Порог отличия пикселя от цвета клетки, чтобы увидеть котика.
CAT_DEVIATION = 70
# Доля «неправильных» пикселей внутри клетки, выше которой это котик.
CAT_AREA_RATIO = 0.15
# Крестик тоже отличается от цвета клетки, и от одного этого признака он не
# отличается: 53% его пикселей белые. Различает котика тёмная морда — у
# проверенных котиков 44-52% пикселей темнее этого порога, у крестика ноль.
CAT_DARK_VALUE = 140
CAT_DARK_RATIO = 0.15


class BoardReadError(RuntimeError):
    """Поле прочитать не удалось. Тапать в такой ситуации нельзя."""


@dataclass(frozen=True)
class Board:
    n: int
    colors: tuple[tuple[str, ...], ...]
    cats: frozenset[tuple[int, int]]
    centers: tuple[tuple[float, float], ...]
    tap_points: tuple[tuple[float, float], ...]
    palette: tuple[tuple[int, int, int], ...]
    cell_w: int
    cell_h: int

    def box(self, row: int, col: int) -> tuple[int, int, int, int]:
        """Прямоугольник клетки: левый верхний угол и размер."""
        cx, cy = self.centers[row * self.n + col]
        return (
            int(cx - self.cell_w / 2),
            int(cy - self.cell_h / 2),
            self.cell_w,
            self.cell_h,
        )

    def cell(self, row: int, col: int) -> str:
        return self.colors[row][col]

    def tap_point(self, row: int, col: int) -> tuple[float, float]:
        return self.tap_points[row * self.n + col]

    def __str__(self) -> str:
        lines = [f"N = {self.n}, котов найдено: {len(self.cats)}"]
        lines.append("")
        lines.append("   " + " ".join(f"{c:>2}" for c in "ABCDEFGHIJKLMNOP"[: self.n]))
        for row in range(self.n):
            mark = ""
            if self.cats:
                mark = "   котики: " + ", ".join(
                    f"({r},{c})" for r, c in sorted(self.cats) if r == row
                )
            lines.append(
                f"{row:>2} " + " ".join(f"{self.colors[row][c]:>2}" for c in range(self.n)) + mark
            )
        return "\n".join(lines)


def _cluster(values: list[float], gap: float) -> list[float]:
    """Свести отсортированные координаты к средним по кластерам."""
    clusters: list[list[float]] = [[values[0]]]
    for value in values[1:]:
        if value - clusters[-1][-1] < gap:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [float(np.mean(cluster)) for cluster in clusters]


def _find_cells(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Найти прямоугольники клеток как связные компоненты по маске насыщенности."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 1].astype(np.int16) > MIN_SATURATION)
        & (hsv[:, :, 2].astype(np.int16) > MIN_VALUE)
    ).astype(np.uint8)

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)

    boxes = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        if area < MIN_CELL_AREA:
            continue
        if not ASPECT_LO < w / h < ASPECT_HI:
            continue
        boxes.append((int(x), int(y), int(w), int(h)))

    if not boxes:
        raise BoardReadError("Не найдено ни одной клетки")

    median_w = float(np.median([b[2] for b in boxes]))
    median_h = float(np.median([b[3] for b in boxes]))

    boxes = [
        b
        for b in boxes
        if abs(b[2] - median_w) < SIZE_TOLERANCE * median_w
        and abs(b[3] - median_h) < SIZE_TOLERANCE * median_h
    ]

    if not boxes:
        raise BoardReadError("Не осталось клеток после отсева по размеру")

    return boxes


def _grid_of(boxes: list[tuple[int, int, int, int]]) -> tuple[int, dict]:
    """Разложить боксы по строкам и столбцам. Возвращает N и клетку на (r, c).

    Клетку с котиком маска насыщенности может не найти: морда котика серая,
    и клетка распадается на мелкие куски. Тогда сетку достраиваем по найденным
    соседям — центры строк и столбцов уже известны, размер клетки тоже.
    """
    cell_h = float(np.median([b[3] for b in boxes]))
    cell_w = float(np.median([b[2] for b in boxes]))

    row_centers = _cluster(sorted(b[1] + b[3] / 2 for b in boxes), cell_h * 0.4)
    col_centers = _cluster(sorted(b[0] + b[2] / 2 for b in boxes), cell_w * 0.4)

    n_rows = len(row_centers)
    n_cols = len(col_centers)

    if n_rows != n_cols:
        raise BoardReadError(f"Поле не квадратное: {n_rows} строк, {n_cols} столбцов")

    n = n_rows
    grid: dict[tuple[int, int], tuple[int, int, int, int]] = {}

    for box in boxes:
        cy = box[1] + box[3] / 2
        cx = box[0] + box[2] / 2
        row = int(np.argmin([abs(cy - y) for y in row_centers]))
        col = int(np.argmin([abs(cx - x) for x in col_centers]))
        if (row, col) in grid:
            raise BoardReadError(f"Две клетки попали в одну позицию ({row},{col})")
        grid[(row, col)] = box

    if len(grid) != n * n:
        missing = [
            (row, col) for row in range(n) for col in range(n) if (row, col) not in grid
        ]
        if not _grid_is_regular(row_centers, col_centers, cell_w, cell_h):
            raise BoardReadError(
                f"Найдено {len(grid)} клеток, а {n}x{n} = {n * n}, "
                f"и достроить не выходит: нерегулярная сетка"
            )

        width = int(round(cell_w))
        height = int(round(cell_h))
        for row, col in missing:
            cy = row_centers[row]
            cx = col_centers[col]
            grid[(row, col)] = (
                int(round(cx - width / 2)),
                int(round(cy - height / 2)),
                width,
                height,
            )

    return n, grid


def _grid_is_regular(
    row_centers: list[float],
    col_centers: list[float],
    cell_w: float,
    cell_h: float,
) -> bool:
    """Ровные ли шаги между соседними строками и столбцами."""
    for centers, cell in ((row_centers, cell_h), (col_centers, cell_w)):
        steps = [b - a for a, b in zip(centers, centers[1:])]
        if not steps:
            continue
        median = float(np.median(steps))
        if any(abs(step - median) > cell * 0.2 for step in steps):
            return False

    return True


def _ring_pixels(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Пиксели по краю клетки: их цвет не испорчен ни котиком, ни скруглением."""
    x, y, w, h = box
    t = max(3, int(min(w, h) * RING_RATIO))
    strips = [
        image[y : y + t, x : x + w],
        image[y + h - t : y + h, x : x + w],
        image[y : y + h, x : x + t],
        image[y : y + h, x + w - t : x + w],
    ]
    return np.concatenate([s.reshape(-1, 3) for s in strips])


def _mode_color(pixels: np.ndarray) -> np.ndarray:
    """Самая частая квантованная клетка цвета.

    Медиана тут не годится: белый бордюр клетки и скруглённые углы занимают
    заметную долю выборки и утягивают медиану в сторону фона.
    """
    quantized = pixels // COLOR_QUANTUM * COLOR_QUANTUM
    values, counts = np.unique(quantized, axis=0, return_counts=True)
    return values[int(np.argmax(counts))].astype(np.float32)


def _has_cat(image: np.ndarray, box: tuple[int, int, int, int], color: np.ndarray) -> bool:
    """Есть ли в клетке котик, а не крестик.

    Два признака, оба нужны:
      - много пикселей, отличных от цвета клетки: и у котика, и у крестика,
      - много тёмных пикселей: у котика чёрно-белая морда, у крестика
        только белые штрихи, и ни один его пиксель не темнее 140.
    """
    x, y, w, h = box
    inner = image[
        y + int(h * 0.25) : y + int(h * 0.75),
        x + int(w * 0.25) : x + int(w * 0.75),
    ].reshape(-1, 3).astype(np.float32)

    if inner.size == 0:
        return False

    deviation = np.abs(inner - color).sum(axis=1)
    if float((deviation > CAT_DEVIATION).mean()) <= CAT_AREA_RATIO:
        return False

    return float((inner.max(axis=1) < CAT_DARK_VALUE).mean()) > CAT_DARK_RATIO


def _build_palette(samples: dict[tuple[int, int], np.ndarray]) -> list[np.ndarray]:
    """Собрать палитру: цвета, отличающиеся друг от друга сильнее порога."""
    palette: list[np.ndarray] = []
    for key in sorted(samples):
        color = samples[key]
        if all(np.abs(existing - color).sum() >= PALETTE_TOLERANCE for existing in palette):
            palette.append(color)
    return palette


def _letter(index: int) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[index]


def _check_regions_contiguous(n: int, colors: tuple[tuple[str, ...], ...]) -> None:
    """Каждый цвет должен образовывать одну связную область.

    Разрыв внутри цвета означает, что палитра считана неверно: два разных
    цвета слились в один. Это главный признак плохого чтения поля.
    """
    for letter in sorted({c for row in colors for c in row}):
        cells = {(r, c) for r in range(n) for c in range(n) if colors[r][c] == letter}
        seen: set[tuple[int, int]] = set()

        for start in sorted(cells):
            if start in seen:
                continue
            stack = [start]
            seen.add(start)
            while stack:
                r, c = stack.pop()
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    neighbor = (r + dr, c + dc)
                    if neighbor in cells and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)

        if len(seen) != len(cells):
            raise BoardReadError(f"Цвет {letter} распался на несколько областей")


def read_board(path: str) -> Board:
    """Прочитать поле со скриншота.

    Бросает BoardReadError, если поле не распозналось или распозналось
    сомнительно. Лучше остановиться, чем тапать наугад: в игре три жизни.
    """
    image = cv2.imread(path)
    if image is None:
        raise BoardReadError(f"Не удалось открыть скриншот {path}")

    boxes = _find_cells(image)
    n, grid = _grid_of(boxes)

    samples = {
        (r, c): _mode_color(_ring_pixels(image, grid[(r, c)]))
        for r in range(n)
        for c in range(n)
    }
    palette = _build_palette(samples)

    if len(palette) != n:
        raise BoardReadError(
            f"В палитре {len(palette)} цветов, а клеток в строке {n}. "
            "Цвета прочитаны неверно"
        )

    colors = tuple(
        tuple(
            _letter(
                min(
                    range(len(palette)),
                    key=lambda t: float(np.abs(palette[t] - samples[(r, c)]).sum()),
                )
            )
            for c in range(n)
        )
        for r in range(n)
    )
    _check_regions_contiguous(n, colors)

    cats = frozenset(
        (r, c)
        for r in range(n)
        for c in range(n)
        if _has_cat(image, grid[(r, c)], samples[(r, c)])
    )

    # Котиков ровно N, и больше на поле быть не может. Если нашлось больше —
    # это не поле, а экран с подсветкой поверх: на таком бот видел 21
    # «котика» на доске 10x10 с надписью «10 кошек».
    if len(cats) > n:
        raise BoardReadError(
            f"Нашлось {len(cats)} котиков на поле {n}x{n}, а котиков ровно {n}. "
            "Это не игровое поле"
        )

    centers = []
    tap_points = []
    for r in range(n):
        for c in range(n):
            x, y, w, h = grid[(r, c)]
            cx = x + w / 2
            cy = y + h / 2
            unit = min(w, h)
            centers.append((cx, cy))
            tap_points.append((cx + TAP_OFFSET_X * unit, cy + TAP_OFFSET_Y * unit))

    cell_w = int(np.median([b[2] for b in boxes]))
    cell_h = int(np.median([b[3] for b in boxes]))

    return Board(
        n=n,
        colors=colors,
        cats=cats,
        centers=tuple(centers),
        tap_points=tuple(tap_points),
        palette=tuple(tuple(int(v) for v in color) for color in palette),
        cell_w=cell_w,
        cell_h=cell_h,
    )


def read_or_none(path: str) -> Optional[Board]:
    """Прочитать поле, вернуть None если не получилось.

    Удобно в игровом цикле: поле исчезло с экрана — значит уровень
    закончился, и это не ошибка.
    """
    try:
        return read_board(path)
    except BoardReadError:
        return None