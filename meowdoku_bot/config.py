import os
from dataclasses import dataclass, fields, replace
from pathlib import Path

ENV_PREFIX = "MEOWDOKU_"

DEFAULT_LOG_FILE = Path("img/tmp/bot.log")


@dataclass(frozen=True)
class BoardReadingSettings:
    """Пороги поиска"""

    min_saturation: int = 40
    min_value: int = 60

    min_cell_area: int = 500
    aspect_min: float = 0.75
    aspect_max: float = 1.33

    size_tolerance: float = 0.15
    grid_step_tolerance: float = 0.2
    ring_ratio: float = 0.10
    color_quantum: int = 8
    palette_tolerance: int = 50


@dataclass(frozen=True)
class CatDetectionSettings:
    """Пороги отличия котика от пустой клетки и от крестика."""

    deviation: int = 70
    area_ratio: float = 0.15
    dark_value: int = 140
    dark_ratio: float = 0.15


@dataclass(frozen=True)
class ScreenDetectionSettings:
    """Пороги поиска кнопки и надписи на служебных экранах."""

    button_hue_min: int = 8
    button_hue_max: int = 22

    button_min_saturation: int = 150
    button_min_value: int = 180
    button_min_area: int = 40000
    button_min_width_ratio: float = 0.5
    button_min_center_y_ratio: float = 0.6
    button_min_fill: float = 0.75
    button_min_aspect: float = 2.0

    button_close_kernel: int = 25

    hint_hue_min: int = 18
    hint_hue_max: int = 32

    hint_min_saturation: int = 120
    hint_min_value: int = 180
    hint_min_width: int = 200

    hint_scan_from_y_ratio: float = 0.75

    hint_tap_offset_y: int = 30


@dataclass(frozen=True)
class TimingSettings:

    poll_interval: float = 1.0

    reaction_timeout: float = 6.0

    max_tap_attempts: int = 3
    max_screen_retries: int = 6
    max_stuck_transitions: int = 3

    double_tap_delay: float = 0.08

    tap_settle: float = 0.35

    solve_time_limit: float = 30.0

    min_board_size: int = 4
    max_board_size: int = 20


@dataclass(frozen=True)
class DeviceSettings:
    """Пути и задержки работы с телефоном."""

    device_dir: str = "/sdcard/meowdoku"
    device_file: str = "/sdcard/meowdoku/screen.png"

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
        return "\n".join(f"  {name} = {value}" for name, value in self.to_dict().items())


def _parse(raw: str) -> object:
    for convert in (int, float):
        try:
            return convert(raw)

        except ValueError:
            continue

    return raw


def from_env(base: Settings | None = None) -> Settings:
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
        from meowdoku_bot.logging_setup import get_logger

        get_logger("config").info(
            "настройки переопределены из окружения: %s", ", ".join(changed)
        )

    return Settings(**groups)
