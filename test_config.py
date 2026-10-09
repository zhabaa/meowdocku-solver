"""Тесты настроек: значения, группы и переопределение из окружения.

Запуск: .venv/bin/python test_config.py
"""

import os
from contextlib import contextmanager
from dataclasses import FrozenInstanceError

from config import Settings, from_env

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


@contextmanager
def environment(**values: str):
    """Временно выставить переменные окружения."""
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_defaults_are_sane() -> None:
    """Значения по умолчанию совпадают с проверенными на живом телефоне."""
    settings = Settings()

    check(settings.board.min_saturation == 40, "порог насыщенности по умолчанию не 40")
    check(settings.board.size_tolerance == 0.15, "допуск по размеру клетки не 0.15")
    check(settings.cat.deviation == 70, "порог отличия пикселя не 70")
    check(settings.cat.dark_value == 140, "порог тёмного пикселя не 140")
    check(settings.cat.dark_ratio == 0.15, "доля тёмных пикселей не 0.15")
    check(settings.screen.button_min_fill == 0.75, "заливка кнопки не 0.75")
    check(settings.screen.button_min_aspect == 2.0, "пропорции кнопки не 2.0")
    check(settings.timing.poll_interval == 1.0, "интервал опроса не 1.0")
    check(settings.timing.max_tap_attempts == 3, "повторов тапа не 3")
    check(settings.timing.max_screen_retries == 4, "повторов экрана не 4")
    check(settings.timing.min_board_size == 4, "минимум поля не 4")
    check(settings.device.device_dir == "/sdcard/meowdoku", "папка на устройстве не та")


def test_settings_are_frozen() -> None:
    settings = Settings()
    try:
        settings.timing.poll_interval = 5.0  # type: ignore[misc]
        failures.append("настройки можно изменить, а должны быть неизменяемыми")
    except FrozenInstanceError:
        pass


def test_all_values_reachable() -> None:
    """Каждое поле видно через to_dict с путём групп."""
    names = set(Settings().to_dict())
    expected = {
        "board.min_saturation",
        "board.size_tolerance",
        "cat.dark_ratio",
        "screen.button_min_fill",
        "timing.poll_interval",
        "device.device_dir",
    }
    check(expected <= names, f"в to_dict нет {expected - names}")
    check(len(names) == 43, f"значений {len(names)}, ожидалось 43")


def test_describe_is_readable() -> None:
    text = Settings().describe()
    check("board.min_saturation = 40" in text, "describe не показывает значения")
    check(len(text.splitlines()) == 43, "describe печатает не все настройки")


def test_from_env_overrides() -> None:
    with environment(MEOWDOKU_CAT_DARK_RATIO="0.25", MEOWDOKU_TIMING_POLL_INTERVAL="2.5"):
        settings = from_env()

    check(settings.cat.dark_ratio == 0.25, "доля тёмных пикселей не переопределена")
    check(settings.timing.poll_interval == 2.5, "интервал опроса не переопределён")
    check(settings.board.min_saturation == 40, "остальные настройки должны остаться как были")


def test_from_env_keeps_strings() -> None:
    with environment(MEOWDOKU_DEVICE_WORK_DIR="logs"):
        settings = from_env()

    check(settings.device.work_dir == "logs", "строковое значение не переопределено")


def test_from_env_without_changes() -> None:
    with environment(MEOWDOKU_BOGUS_SETTING="1"):
        settings = from_env()

    check(settings.to_dict() == Settings().to_dict(), "неизвестная переменная что-то изменила")


def test_from_env_accepts_base() -> None:
    """Переопределение поверх переданных настроек, а не поверх дефолтов."""
    from dataclasses import replace

    base = replace(Settings(), board=replace(Settings().board, min_saturation=99))
    with environment(MEOWDOKU_CAT_DARK_RATIO="0.3"):
        settings = from_env(base)

    check(settings.board.min_saturation == 99, "базовые настройки потерялись")
    check(settings.cat.dark_ratio == 0.3, "переопределение не применилось к базе")


def main() -> int:
    for test in (
        test_defaults_are_sane,
        test_settings_are_frozen,
        test_all_values_reachable,
        test_describe_is_readable,
        test_from_env_overrides,
        test_from_env_keeps_strings,
        test_from_env_without_changes,
        test_from_env_accepts_base,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты настроек прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
