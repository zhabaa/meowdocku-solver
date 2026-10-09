"""Определение того, что сейчас на экране телефона.

В игре четыре состояния:
  - поле: видны цветные клетки, считываем расстановку,
  - уровень пройден: оранжевая кнопка внизу,
  - таблица лидеров: жёлтая надпись «Нажмите, чтобы продолжить»,
  - неизвестно: ничего не узнали, тапать нельзя.

Точки тапов ищутся по картинке, а не заданы числами: кнопка бывает и
«Золотая рыбка», и «Уровень 334», но выглядит одинаково.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import cv2
import numpy as np

from .config import ScreenDetectionSettings, Settings
from .domain import ScreenKind
from .field import Board, BoardReadError, BoardReader
from .logging_setup import get_logger

log = get_logger("screens")


class Screen(ABC):
    """Что сейчас на экране."""

    kind: ScreenKind

    @property
    def tap_point(self) -> tuple[int, int] | None:
        """Куда тапать, чтобы продолжить. У поля и непонятного экрана — никуда."""
        return None

    def describe(self) -> str:
        return str(self.kind)


class BoardScreen(Screen):
    """Игровое поле: видны цветные клетки."""

    kind = ScreenKind.BOARD

    def __init__(self, board: Board) -> None:
        self.board = board

    def describe(self) -> str:
        return f"поле {self.board.size}x{self.board.size}"


class TapScreen(Screen):
    """Служебный экран, с которого можно тапнуть и уйти дальше."""

    def __init__(self, kind: ScreenKind, point: tuple[int, int], what: str) -> None:
        self.kind = kind
        self._point = point
        self.what = what

    @property
    def tap_point(self) -> tuple[int, int]:
        return self._point

    def describe(self) -> str:
        return f"{self.what}, тап в {self._point}"


class LevelDoneScreen(TapScreen):
    """Экран «уровень пройден»."""

    kind = ScreenKind.LEVEL_DONE

    def __init__(self, point: tuple[int, int]) -> None:
        super().__init__(ScreenKind.LEVEL_DONE, point, "уровень пройден")


class LeaderboardScreen(TapScreen):
    """Таблица лидеров с надписью «нажмите, чтобы продолжить»."""

    kind = ScreenKind.LEADERBOARD

    def __init__(self, point: tuple[int, int]) -> None:
        super().__init__(ScreenKind.LEADERBOARD, point, "таблица лидеров")


class UnknownScreen(Screen):
    """Ничего не узнали. Тапать сюда нельзя."""

    kind = ScreenKind.UNKNOWN

    def __init__(self, reason: str) -> None:
        self.reason = reason

    def describe(self) -> str:
        return f"не опознан: {self.reason}"


class ScreenClassifier:
    """Отличает поле, служебные экраны и непонятное."""

    def __init__(self, settings: Settings | None = None, reader: BoardReader | None = None) -> None:
        resolved = settings or Settings()
        self.settings = resolved.screen
        self.reader = reader or BoardReader(resolved)

    def classify(self, path: str | Path) -> Screen:
        """Определить, что на экране по файлу.

        Порядок важен: сначала кнопка, потом надпись, и только потом пробуем
        читать поле. На экране пройденного уровня поле видно, но затемнено,
        и читается оно не как поле — проверка кнопки срабатывает раньше.
        """
        image = self._load(path)

        button = self.find_level_done_button(image)
        if button is not None:
            return LevelDoneScreen(button)

        hint = self.find_continue_hint(image)
        if hint is not None:
            return LeaderboardScreen(hint)

        try:
            board = self.reader.read(image)
        except BoardReadError as error:
            log.debug("поле не прочиталось: %s", error)
            return UnknownScreen(str(error))

        return BoardScreen(board)

    def find_level_done_button(self, image: np.ndarray) -> tuple[int, int] | None:
        """Центр оранжевой кнопки в нижней половине экрана."""
        mask = self._orange_mask(image)
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            np.ones((self.settings.button_close_kernel,) * 2, np.uint8),
        )

        count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
        height, width = image.shape[:2]

        for index in range(1, count):
            left, top, button_width, button_height, area = stats[index]
            center_y = top + button_height // 2

            if area <= self.settings.button_min_area:
                continue
            if button_width <= width * self.settings.button_min_width_ratio:
                continue
            if center_y <= height * self.settings.button_min_center_y_ratio:
                continue
            # Кнопка — плотный прямоугольник: залита почти целиком и сильно
            # шире, чем выше. Эти две проверки отсекают слипшиеся жёлтые
            # клетки поля: они дают широкий блок в нижней половине, но
            # залиты меньше чем наполовину.
            if area / float(button_width * button_height) < self.settings.button_min_fill:
                continue
            if button_width / float(button_height) < self.settings.button_min_aspect:
                continue

            return (int(left + button_width // 2), int(center_y))

        return None

    def find_continue_hint(self, image: np.ndarray) -> tuple[int, int] | None:
        """Точка тапа по жёлтой надписи «нажмите, чтобы продолжить»."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = (
            (hsv[:, :, 0] >= self.settings.hint_hue_min)
            & (hsv[:, :, 0] <= self.settings.hint_hue_max)
            & (hsv[:, :, 1] > self.settings.hint_min_saturation)
            & (hsv[:, :, 2] > self.settings.hint_min_value)
        ).astype(np.uint8)

        for y in range(int(image.shape[0] * self.settings.hint_scan_from_y_ratio), image.shape[0]):
            xs = np.where(mask[y] > 0)[0]
            if len(xs) > self.settings.hint_min_width:
                center = (int((xs.min() + xs.max()) // 2), int(y + self.settings.hint_tap_offset_y))
                return center

        return None

    def _orange_mask(self, image: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        return (
            (hsv[:, :, 0] >= self.settings.button_hue_min)
            & (hsv[:, :, 0] <= self.settings.button_hue_max)
            & (hsv[:, :, 1] > self.settings.button_min_saturation)
            & (hsv[:, :, 2] > self.settings.button_min_value)
        ).astype(np.uint8)

    @staticmethod
    def _load(path: str | Path) -> np.ndarray:
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"не удалось открыть {path}")
        return image


def detect(path: str | Path) -> Screen:
    """Определить экран — короткий вызов для скриптов и тестов."""
    return ScreenClassifier().classify(path)
