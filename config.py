"""Все пороги бота в одном месте.

Раньше 25 констант лежали в трёх файлах, и найти нужную можно было только
по всему коду. Здесь у каждого значения есть имя и объяснение, откуда оно
взялось.

Переопределить без правки кода — через переменные окружения с префиксом
MEOWDOKU_, например:

    MEOWDOKU_CAT_DARK_RATIO=0.2 .venv/bin/python main.py
"""

import os
from dataclasses import dataclass, fields, replace

ENV_PREFIX = "MEOWDOKU_"


@dataclass(frozen=True)
class BoardReadingSettings:
    """Пороги поиска клеток и цветов в снимке экрана."""

    # Клетки насыщенные, фон и рамки бледные. Первая версия брала порог
    # яркости 220, и мимо проходили иконки котиков вверху и кнопки внизу.
    min_saturation: int = 40
    min_value: int = 60

    # Мелкие компоненты пропускаем: пыль, подсветка, отдельные пиксели.
    min_cell_area: int = 500
    # Допуск по пропорциям сторон. Клетка квадратная, но снимок слегка
    # смазан, и стороны отличаются на пару пикселей.
    aspect_min: float = 0.75
    aspect_max: float = 1.33
    # Допуск по размеру клетки. Внутри одного поля клетки отличаются на
    # пиксель, а посторонние квадратики — на десятки. При 0.3 проходил
    # лишний квадрат 70x70 рядом с клетками 94x95, и поле читалось как
    # 11 строк вместо 10.
    size_tolerance: float = 0.15
    # Насколько шаг между соседними строками может отличаться от
    # медианного. По этому признаку решаем, достраивать ли сетку.
    grid_step_tolerance: float = 0.2
    # Кольцо по краю клетки: внутренняя часть исключена, там рисуется котик.
    ring_ratio: float = 0.10
    # Квантование цвета при поиске моды, иначе шум плодит ложные цвета.
    color_quantum: int = 8
    # Порог разницы цветов при кластеризации палитры.
    palette_tolerance: int = 50


@dataclass(frozen=True)
class CatDetectionSettings:
    """Пороги отличия котика от пустой клетки и от крестика."""

    # Порог отличия пикселя от цвета клетки.
    deviation: int = 70
    # Доля «неправильных» пикселей внутри клетки, выше которой это котик.
    area_ratio: float = 0.15
    # Крестик тоже отличается от цвета клетки, и от одного этого признака
    # он не отличается: 53% его пикселей белые. Различает котика тёмная
    # морда — у проверенных котиков 44-52% пикселей темнее этого порога,
    # у крестика ноль.
    dark_value: int = 140
    dark_ratio: float = 0.15


@dataclass(frozen=True)
class ScreenDetectionSettings:
    """Пороги поиска кнопки и надписи на служебных экранах."""

    # Оранжевая кнопка «уровень пройден».
    button_hue_min: int = 8
    button_hue_max: int = 22
    button_min_saturation: int = 150
    button_min_value: int = 180
    button_min_area: int = 40000
    button_min_width_ratio: float = 0.5
    button_min_center_y_ratio: float = 0.6
    button_close_kernel: int = 25
    # Кнопка — плотный прямоугольник: залита почти целиком и сильно шире,
    # чем выше. Эти две проверки отсекают слипшиеся жёлтые клетки поля.
    button_min_fill: float = 0.75
    button_min_aspect: float = 2.0

    # Жёлтая надпись «нажмите, чтобы продолжить» на экране лидеров.
    hint_hue_min: int = 18
    hint_hue_max: int = 32
    hint_min_saturation: int = 120
    hint_min_value: int = 180
    hint_min_width: int = 200
    hint_scan_from_y_ratio: float = 0.75
    # Тап чуть ниже самой надписи: попадать в текст надёжнее, чем в пустое место.
    hint_tap_offset_y: int = 30


@dataclass(frozen=True)
class TimingSettings:
    """Паузы и повторы. Подобраны на живом телефоне."""

    # Как часто опрашивать экран, пока ждём реакцию игры.
    poll_interval: float = 1.0
    # Сколько секунд ждать реакции, прежде чем повторить тап.
    reaction_timeout: float = 6.0
    # Сколько повторов тапа подряд, прежде чем сдаться.
    max_tap_attempts: int = 3
    # Сколько раз переснять экран, если он не опознался: во время анимации
    # перехода между экранами кадр читается плохо и через пару секунд нормально.
    max_screen_retries: int = 4
    # Пауза между двумя нажатиями в двойном тапе.
    double_tap_delay: float = 0.08
    # Пауза после двойного тапа: нужно дождаться реакции игры.
    tap_settle: float = 0.35
    # Предел поиска расстановки.
    solve_time_limit: float = 30.0
    # Настоящие поля не меньше 4x4. Меньшие — ореолы вокруг иконок
    # на переходных кадрах, а не доски.
    min_board_size: int = 4
    max_board_size: int = 20


@dataclass(frozen=True)
class DeviceSettings:
    """Пути и задержки работы с телефоном."""

    # Куда на устройстве складываем скриншоты. В /data доступа у обычного
    # приложения нет, поэтому только /sdcard.
    device_dir: str = "/sdcard/meowdoku"
    device_file: str = "/sdcard/meowdoku/screen.png"
    # Папка на компьютере для скриншотов и логов.
    work_dir: str = "img/tmp"


@dataclass(frozen=True)
class Settings:
    """Полный набор настроек бота."""

    board: BoardReadingSettings = BoardReadingSettings()
    cat: CatDetectionSettings = CatDetectionSettings()
    screen: ScreenDetectionSettings = ScreenDetectionSettings()
    timing: TimingSettings = TimingSettings()
    device: DeviceSettings = DeviceSettings()

    def to_dict(self) -> dict[str, object]:
        """Все значения по именам, для логов и отладки."""
        return {
            f"{group_name}.{item.name}": getattr(group, item.name)
            for group_name, group in self.groups().items()
            for item in fields(group)
        }

    def groups(self) -> dict[str, object]:
        return {
            "board": self.board,
            "cat": self.cat,
            "screen": self.screen,
            "timing": self.timing,
            "device": self.device,
        }

    def describe(self) -> str:
        """Настройки строками — для файла лога."""
        return "\n".join(f"  {name} = {value}" for name, value in self.to_dict().items())


def _parse(raw: str) -> object:
    """Превратить строку из окружения в число или оставить как есть."""
    for convert in (int, float):
        try:
            return convert(raw)
        except ValueError:
            continue
    return raw


def from_env(base: Settings | None = None) -> Settings:
    """Взять настройки и переопределить их из переменных окружения.

    Имя переменной — путь до поля через точку, заглавными буквами:
    MEOWDOKU_CAT_DARK_RATIO, MEOWDOKU_TIMING_POLL_INTERVAL и так далее.
    """
    settings = base or Settings()
    groups = settings.groups()
    changed: list[str] = []

    for group_name, group in groups.items():
        replacements = {}

        for item in fields(group):
            env_name = f"{ENV_PREFIX}{group_name.upper()}_{item.name.upper()}"
            if env_name not in os.environ:
                continue
            replacements[item.name] = _parse(os.environ[env_name])
            changed.append(f"{env_name}={os.environ[env_name]}")

        if replacements:
            groups[group_name] = replace(group, **replacements)

    if changed:
        from logging_setup import get_logger

        get_logger("config").info(
            "настройки переопределены из окружения: %s", ", ".join(changed)
        )

    return Settings(**groups)
