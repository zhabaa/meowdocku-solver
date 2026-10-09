"""Определение того, что сейчас на экране телефона.

В игре четыре состояния:
  - поле: видны цветные клетки, считываем расстановку,
  - уровень пройден: оранжевая кнопка внизу,
  - таблица лидеров: жёлтая надпись «Нажмите, чтобы продолжить»,
  - неизвестно: ничего не узнали, тапать нельзя.

Точки тапов ищутся по картинке, а не заданы числами: кнопка бывает и
«Золотая рыбка», и «Уровень 334», но выглядит одинаково.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import cv2
import numpy as np

from field import Board, BoardReadError, read_board

# Оранжевая кнопка: оттенок, насыщенность, яркость.
BUTTON_HUE_LO, BUTTON_HUE_HI = 8, 22
BUTTON_MIN_SAT, BUTTON_MIN_VAL = 150, 180
BUTTON_MIN_AREA = 40000
BUTTON_MIN_WIDTH_RATIO = 0.5
BUTTON_MIN_CENTER_Y_RATIO = 0.6
BUTTON_CLOSE_KERNEL = 25

# Жёлтая надпись на лидерах.
HINT_HUE_LO, HINT_HUE_HI = 18, 32
HINT_MIN_SAT, HINT_MIN_VAL = 120, 180
HINT_MIN_WIDTH = 200
HINT_SCAN_FROM_Y_RATIO = 0.75
# Тап чуть ниже самой надписи: попадать в текст надёжнее, чем в пустое место.
HINT_TAP_OFFSET_Y = 30


class ScreenKind:
    BOARD = "board"
    LEVEL_DONE = "level_done"
    LEADERBOARD = "leaderboard"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class BoardScreen:
    kind: str
    board: Board


@dataclass(frozen=True)
class TapScreen:
    kind: str
    point: tuple[int, int]


@dataclass(frozen=True)
class UnknownScreen:
    kind: str
    reason: str


Screen = Union[BoardScreen, TapScreen, UnknownScreen]


def _load(path: str | Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise FileNotFoundError(f"Не удалось открыть {path}")
    return image


def find_level_done_button(image: np.ndarray) -> Optional[tuple[int, int]]:
    """Центр оранжевой кнопки в нижней половине экрана."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 0] >= BUTTON_HUE_LO)
        & (hsv[:, :, 0] <= BUTTON_HUE_HI)
        & (hsv[:, :, 1] > BUTTON_MIN_SAT)
        & (hsv[:, :, 2] > BUTTON_MIN_VAL)
    ).astype(np.uint8)

    kernel = np.ones((BUTTON_CLOSE_KERNEL, BUTTON_CLOSE_KERNEL), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    height, width = image.shape[:2]

    for i in range(1, count):
        x, y, w, h, area = stats[i]
        center_y = y + h // 2
        if (
            area > BUTTON_MIN_AREA
            and w > width * BUTTON_MIN_WIDTH_RATIO
            and center_y > height * BUTTON_MIN_CENTER_Y_RATIO
        ):
            return (int(x + w // 2), int(center_y))

    return None


def find_continue_hint(image: np.ndarray) -> Optional[tuple[int, int]]:
    """Точка тапа по жёлтой надписи «Нажмите, чтобы продолжить»."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = (
        (hsv[:, :, 0] >= HINT_HUE_LO)
        & (hsv[:, :, 0] <= HINT_HUE_HI)
        & (hsv[:, :, 1] > HINT_MIN_SAT)
        & (hsv[:, :, 2] > HINT_MIN_VAL)
    ).astype(np.uint8)

    for y in range(int(image.shape[0] * HINT_SCAN_FROM_Y_RATIO), image.shape[0]):
        xs = np.where(mask[y] > 0)[0]
        if len(xs) > HINT_MIN_WIDTH:
            return (int((xs.min() + xs.max()) // 2), int(y + HINT_TAP_OFFSET_Y))

    return None


def detect(path: str | Path) -> Screen:
    """Определить, что на экране.

    Порядок важен: сначала ищем кнопку, потом надпись, и только потом пробуем
    читать поле. На экране пройденного уровня поле видно, но затемнено, и
    читается оно не как поле — проверка кнопки срабатывает раньше.
    """
    image = _load(path)

    button = find_level_done_button(image)
    if button is not None:
        return TapScreen(kind=ScreenKind.LEVEL_DONE, point=button)

    hint = find_continue_hint(image)
    if hint is not None:
        return TapScreen(kind=ScreenKind.LEADERBOARD, point=hint)

    try:
        board = read_board(str(path))
    except BoardReadError as error:
        return UnknownScreen(kind=ScreenKind.UNKNOWN, reason=str(error))

    return BoardScreen(kind=ScreenKind.BOARD, board=board)