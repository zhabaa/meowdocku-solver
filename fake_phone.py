"""Подделка телефона для тестов цикла.

Настоящий телефон в тестах недоступен, но нужно проверить главное: бот
ставит всех кошек ровно по решению и не повторяет тап, если кот появился.

Подделка честная: берём настоящий скрин пустого поля, а на двойной тап
подставляем в клетку спрайт котика, вырезанный из того же поля с уже
стоящим котом. Скриншот получается почти неотличим от настоящего:
расхождение 0.5% пикселей по краям спрайта.
"""

from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from config import Settings
from domain import Cell
from field import BoardReader

SHOTS = Path(__file__).parent / "img" / "screenshots"

# Поле 8x8 без котиков и то же поле с тремя котиками: разность клеток и
# есть нарисованный котик.
EMPTY_BOARD = SHOTS / "shot_5.jpg"
BOARD_WITH_CATS = SHOTS / "shot_6.jpg"
SOURCE_CATS = ((4, 3), (5, 5), (6, 0))


def _grid_of(image: np.ndarray) -> dict[Cell, "CellBox"]:
    """Публичный способ узнать прямоугольник каждой клетки."""
    reader = BoardReader(Settings())
    boxes = reader.cells_detector.find_cell_boxes(image)
    _size, grid = reader.cells_detector.build_grid(boxes)
    return grid


def build_cat_sprites() -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Вырезать спрайт котика: картинка клетки с котом и маска котика.

    Ключ — сторона клетки, чтобы подходить клеткам любого размера.
    """
    empty = cv2.imread(str(EMPTY_BOARD))
    filled = cv2.imread(str(BOARD_WITH_CATS))

    empty_grid = _grid_of(empty)
    filled_grid = _grid_of(filled)

    sprites: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for row, col in SOURCE_CATS:
        cell = Cell(row, col)
        empty_box = empty_grid[cell]
        filled_box = filled_grid[cell]

        before = empty[
            empty_box.top : empty_box.top + empty_box.height,
            empty_box.left : empty_box.left + empty_box.width,
        ].astype(np.int16)
        after = filled[
            filled_box.top : filled_box.top + empty_box.height,
            filled_box.left : filled_box.left + empty_box.width,
        ]

        difference = np.abs(after.astype(np.int16) - before).sum(axis=2) > 40

        sprite = before.astype(np.uint8)
        sprite[difference] = after[difference]

        sprites.setdefault(min(empty_box.width, empty_box.height), (sprite, difference))

    return sprites


class FakePhone:
    """Телефон, который честно реагирует на тапы и кладёт котиков."""

    def __init__(
        self,
        screens: list[Path] | None = None,
        out: Path | None = None,
        settings: Settings | None = None,
    ):
        # По умолчанию: лидеры, потом пустое поле 8x8.
        self.screens = list(screens) if screens else [
            SHOTS / "shot_1.jpg",
            SHOTS / "shot_5.jpg",
        ]
        self.out = out or Path("img/tmp/fake")
        self.out.mkdir(parents=True, exist_ok=True)

        self.reader = BoardReader(settings or Settings())
        self.sprites = build_cat_sprites()

        self.screen = cv2.imread(str(self.screens[0]))
        self.index = 1

        self.taps: list[tuple[int, int]] = []
        self.double_taps: list[tuple[int, int]] = []

    def is_connected(self) -> bool:
        return True

    def capture(self, destination) -> Path:
        local = Path(destination)
        local.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(local), self.screen)
        return local

    def tap(self, x, y) -> None:
        """Одиночный тап: переходим на следующий экран."""
        self.taps.append((int(x), int(y)))

        if self.index < len(self.screens):
            self.screen = cv2.imread(str(self.screens[self.index]))
            self.index += 1

    def double_tap(self, x, y) -> None:
        """Двойной тап: рисуем котика, если клетка ещё пуста."""
        self.double_taps.append((int(x), int(y)))

        board = self._read_board()
        if board is None:
            return

        cell = self._cell_at(board, x, y)
        if cell is None or (cell.row, cell.col) in board.cats:
            return

        self._draw_cat(board, cell)

    def _read_board(self):
        path = self.out / "probe.png"
        cv2.imwrite(str(path), self.screen)

        try:
            return self.reader.read_path(str(path))
        except Exception:
            return None

    def _cell_at(self, board, x: float, y: float) -> Cell | None:
        """Ближайшая клетка к точке тапа, если тап вообще попал в поле."""
        centers = [
            (board.tap_point(row, col), Cell(row, col))
            for row in range(board.size)
            for col in range(board.size)
        ]
        best_point, best_cell = min(
            centers, key=lambda item: (item[0][0] - x) ** 2 + (item[0][1] - y) ** 2
        )

        limit = board.centers[1][0] - board.centers[0][0]
        if (best_point[0] - x) ** 2 + (best_point[1] - y) ** 2 > limit ** 2:
            return None

        return best_cell

    def _draw_cat(self, board, cell: Cell) -> None:
        cx, cy = board.centers[cell.row * board.size + cell.col]
        x = int(cx - board.cell_w / 2)
        y = int(cy - board.cell_h / 2)
        w, h = board.cell_w, board.cell_h

        sprite, mask = self.sprites.get(int(min(w, h))) or next(iter(self.sprites.values()))

        patch = self.screen[y : y + h, x : x + w]
        if patch.shape[0] != h or patch.shape[1] != w:
            return

        # Спрайт вырезан с другого поля, размер может отличаться: подгоняем.
        if sprite.shape[0] != h or sprite.shape[1] != w:
            sprite = cv2.resize(sprite, (w, h), interpolation=cv2.INTER_LINEAR)
            mask = cv2.resize(mask.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0

        patch[mask] = sprite[mask]

        # Перезаписываем снимок: тот же файл читает и бот, и тест.
        cv2.imwrite(str(self.out / "probe.png"), self.screen)


def patch_all(phone: FakePhone, main_module):
    """Контексты подмены adb-слоя на подделку телефона."""
    return (
        mock.patch.object(main_module.emulate, "is_connected", side_effect=phone.is_connected),
        mock.patch.object(main_module.emulate, "capture", side_effect=phone.capture),
        mock.patch.object(main_module.emulate, "tap", side_effect=phone.tap),
        mock.patch.object(main_module.emulate, "double_tap", side_effect=phone.double_tap),
        mock.patch("time.sleep"),
    )