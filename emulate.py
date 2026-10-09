"""Управление телефоном через adb.

Скриншоты и тапы. Двойной тап в Meowdoku ставит котика, одиночный —
крестик, поэтому одиночный здесь не используется.
"""

import shutil
import subprocess
import time
from pathlib import Path

# Куда на устройстве складываем скриншоты.
DEVICE_DIR = "/sdcard/meowdoku"
DEVICE_FILE = f"{DEVICE_DIR}/screen.png"

# Пауза между двумя тапами в двойном тапе.
DOUBLE_TAP_DELAY = 0.08
# Пауза после двойного тапа: нужно дождаться реакции игры.
TAP_SETTLE = 0.35


class AdbError(RuntimeError):
    """adb отработал с ошибкой или устройство не отвечает."""


def adb(*args: str, check: bool = True, quiet: bool = False) -> str:
    """Вызвать adb и вернуть вывод.

    quiet=True гасит вывод adb в None: нужно, когда команда ничего
    полезного не печатает.
    """
    command = ["adb", *args]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if check and result.returncode != 0:
        raise AdbError(
            f"{' '.join(command)} вернул код {result.returncode}\n{result.stderr.strip()}"
        )

    return "" if quiet else result.stdout


def is_connected() -> bool:
    """Подключён ли телефон."""
    if shutil.which("adb") is None:
        return False

    lines = adb("devices", check=False).splitlines()[1:]
    return any(len(parts := line.split()) >= 2 and parts[1] == "device" for line in lines)


def capture(destination: str | Path, device_ready: bool = True) -> Path:
    """Снять скриншот телефона и сохранить локально.

    Скриншот пишется прямо на устройство в /sdcard, потому что доступа
    к /data у обычного приложения нет, а потом забирается через adb pull.
    """
    local = Path(destination)
    local.parent.mkdir(parents=True, exist_ok=True)

    if device_ready:
        adb("shell", "mkdir", "-p", DEVICE_DIR)
        adb("shell", "screencap", "-p", DEVICE_FILE)
        adb("pull", DEVICE_FILE, str(local))
        adb("shell", "rm", "-f", DEVICE_FILE)
    else:
        raise AdbError("Телефон не подключён")

    if not local.exists() or local.stat().st_size == 0:
        raise AdbError(f"Скриншот не получен: {local}")

    return local


def tap(x: float, y: float) -> None:
    """Одиночный тап. В игре ставит крестик, поэтому сам по себе не нужен."""
    adb("shell", "input", "tap", str(int(x)), str(int(y)))


def double_tap(x: float, y: float) -> None:
    """Двойной тап: ставит котика.

    Оба тапа уходят одной командой adb shell. Два отдельных вызова дают
    между тапами сотни миллисекунд на запуск adb, и игра такой тап
    двойным не считает.
    """
    ix, iy = str(int(x)), str(int(y))
    adb(
        "shell",
        f"input motionevent DOWN {ix} {iy}; "
        f"input motionevent UP {ix} {iy}; "
        f"sleep {DOUBLE_TAP_DELAY}; "
        f"input motionevent DOWN {ix} {iy}; "
        f"input motionevent UP {ix} {iy}",
    )
    time.sleep(TAP_SETTLE)


def wait_for_device(timeout: float = 30.0) -> None:
    """Дождаться, пока телефон появится в adb."""
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if is_connected():
            return
        time.sleep(1.0)

    raise AdbError(f"Телефон не появился за {timeout:.0f}с")