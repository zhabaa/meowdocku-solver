"""Тесты слоя adb: проверяем форму команд, не трогая телефон.

Подменяем subprocess.run, поэтому тесты работают без устройства.

Запуск: .venv/bin/python test_emulate.py
"""

from pathlib import Path
from unittest import mock

import emulate

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


class FakeResult:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_double_tap_is_one_command() -> None:
    """Двойной тап обязан уйти одной командой, иначе между тапами вылезает adb."""
    with mock.patch.object(emulate.subprocess, "run", return_value=FakeResult()) as run:
        emulate.double_tap(100.4, 200.9)

    check(run.call_count == 1, f"ожидался 1 вызов adb, было {run.call_count}")

    command = run.call_args[0][0]
    check(command[0] == "adb", f"команда начинается с {command[0]}")
    check(command[1] == "shell", f"ожидался shell, было {command[1]}")

    script = command[2]
    check(
        script.count("motionevent DOWN") == 2,
        f"ожидались 2 нажатия, в скрипте {script.count('motionevent DOWN')}",
    )
    check(
        script.count("motionevent UP") == 2,
        f"ожидались 2 отпускания, в скрипте {script.count('motionevent UP')}",
    )
    check("100 200" in script, f"координаты не округлены или потеряны: {script}")


def test_capture_writes_to_device_then_pulls() -> None:
    with mock.patch.object(emulate.subprocess, "run", return_value=FakeResult()) as run, \
         mock.patch.object(emulate, "is_connected", return_value=True), \
         mock.patch.object(Path, "mkdir", return_value=None), \
         mock.patch.object(Path, "exists", return_value=True), \
         mock.patch.object(Path, "stat", return_value=mock.Mock(st_size=100)):
        emulate.capture("out/screen.png")

    commands = [call[0][0] for call in run.call_args_list]

    check(
        any("screencap" in c for c in commands),
        f"screencap не вызван: {commands}",
    )
    check(
        any("pull" in c for c in commands),
        f"pull не вызван: {commands}",
    )
    check(
        any("mkdir" in c for c in commands),
        f"папка на устройстве не создана: {commands}",
    )
    check(
        any("rm" in c for c in commands),
        f"временный файл на устройстве не убран: {commands}",
    )


def test_capture_without_device_raises() -> None:
    with mock.patch.object(emulate, "is_connected", return_value=False):
        try:
            emulate.capture("out/screen.png")
            failures.append("без телефона ожидалась ошибка")
        except emulate.AdbError:
            pass


def test_adb_error_is_reported() -> None:
    failing = FakeResult(stderr="device offline", returncode=1)
    with mock.patch.object(emulate.subprocess, "run", return_value=failing):
        try:
            emulate.adb("shell", "true")
            failures.append("ошибка adb не поднята")
        except emulate.AdbError as error:
            check("device offline" in str(error), f"в тексте ошибки нет вывода adb: {error}")


def test_is_connected() -> None:
    outputs = [
        ("List of devices attached\n", False),
        ("List of devices attached\nABC123\tdevice\n", True),
        ("List of devices attached\nABC123\toffline\n", False),
        ("List of devices attached\nABC123\tunauthorized\n", False),
    ]

    for output, expected in outputs:
        with mock.patch.object(emulate.shutil, "which", return_value="/usr/bin/adb"), \
             mock.patch.object(emulate.subprocess, "run", return_value=FakeResult(output)):
            check(
                emulate.is_connected() == expected,
                f"вывод {output!r}: ожидалось {expected}",
            )


def test_wait_for_device_gives_up() -> None:
    with mock.patch.object(emulate, "is_connected", return_value=False), \
         mock.patch.object(emulate.time, "sleep"):
        try:
            emulate.wait_for_device(timeout=0.05)
            failures.append("ожидалась ошибка ожидания устройства")
        except emulate.AdbError:
            pass


def main() -> int:
    for test in (
        test_double_tap_is_one_command,
        test_capture_writes_to_device_then_pulls,
        test_capture_without_device_raises,
        test_adb_error_is_reported,
        test_is_connected,
        test_wait_for_device_gives_up,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты слоя adb прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())