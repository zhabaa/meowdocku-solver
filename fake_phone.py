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

from field import _find_cells, _grid_of, read_board

SHOTS = Path(__file__).parent / "img" / "screenshots"

# Поле 8x8 без котиков и то же поле с тремя котиками: разность клеток и
# есть нарисованный котик.
EMPTY_BOARD = SHOTS / "shot_5.jpg"
BOARD_WITH_CATS = SHOTS / "shot_6.jpg"
SOURCE_CATS = ((4, 3), (5, 5), (6, 0))


def build_cat_sprites() -> dict[int, tuple[np.ndarray, np.ndarray]]:
    """Вырезать спрайт котика: картинка клетки с котом и маска котика.

    Ключ — сторона клетки, чтобы подходить клеткам любого размера.
    """
    empty = cv2.imread(str(EMPTY_BOARD))
    filled = cv2.imread(str(BOARD_WITH_CATS))

    _, empty_grid = _grid_of(_find_cells(empty))
    _, filled_grid = _grid_of(_find_cells(filled))

    sprites: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for cell in SOURCE_CATS:
        x, y, w, h = empty_grid[cell]
        fx, fy, _, _ = filled_grid[cell]

        before = empty[y : y + h, x : x + w].astype(np.int16)
        after = filled[fy : fy + h, fx : fx + w]

        difference = np.abs(after.astype(np.int16) - before).sum(axis=2) > 40

        sprite = before.astype(np.uint8)
        sprite[difference] = after[difference]

        sprites.setdefault(min(w, h), (sprite, difference))

    return sprites


class FakePhone:
    """Телефон, который честно реагирует на тапы и кладёт котиков."""

    def __init__(self, screens: list[Path] | None = None, out: Path | None = None):
        # По умолчанию: лидеры, потом пустое поле 8x8.
        self.screens = list(screens) if screens else [
            SHOTS / "shot_1.jpg",
            SHOTS / "shot_5.jpg",
        ]
        self.out = out or Path("img/tmp/fake")
        self.out.mkdir(parents=True, exist_ok=True)

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
        if cell is None or cell in board.cats:
            return

        self._draw_cat(board, cell)

    def _read_board(self):
        path = self.out / "probe.png"
        cv2.imwrite(str(path), self.screen)

        try:
            return read_board(str(path))
        except Exception:
            return None

    def _cell_at(self, board, x: float, y: float) -> tuple[int, int] | None:
        """Ближайшая клетка к точке тапа, если тап вообще попал в поле."""
        centers = [(board.tap_point(r, c), (r, c)) for r in range(board.n) for c in range(board.n)]
        best = min(centers, key=lambda item: (item[0][0] - x) ** 2 + (item[0][1] - y) ** 2)

        limit = board.centers[1][0] - board.centers[0][0]
        if (best[0][0] - x) ** 2 + (best[0][1] - y) ** 2 > limit**2:
            return None

        return best[1]

    def _draw_cat(self, board, cell: tuple[int, int]) -> None:
        row, col = cell
        cx, cy = board.centers[row * board.n + col]
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