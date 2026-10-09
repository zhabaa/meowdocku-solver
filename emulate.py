"""Управление телефоном через adb.

Скриншоты и тапы. Двойной тап в Meowdoku ставит котика, одиночный —
крестик, поэтому одиночный в игровом цикле не используется.
"""

import shutil
import subprocess
import time
from pathlib import Path

from config import DeviceSettings, Settings, TimingSettings
from logging_setup import get_logger

log = get_logger("device")


class AdbError(RuntimeError):
    """adb отработал с ошибкой или устройство не отвечает."""


class AdbDevice:
    """Телефон, с которым говорим через adb.

    Пути на устройстве и задержки — в конструкторе, чтобы тесты подставляли
    свою подделку вместо настоящего телефона.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        device: DeviceSettings | None = None,
        timing: TimingSettings | None = None,
    ) -> None:
        resolved = settings or Settings()
        self.device = device or resolved.device
        self.timing = timing or resolved.timing
        self.executable = "adb"

    # --- adb ---------------------------------------------------------------

    def adb(self, *args: str, check: bool = True) -> str:
        """Вызвать adb и вернуть вывод."""
        command = [self.executable, *args]
        log.debug("adb %s", " ".join(args))

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

        if check and result.returncode != 0:
            log.error("adb %s вернул %d: %s", " ".join(args), result.returncode, result.stderr.strip())
            raise AdbError(
                f"{' '.join(command)} вернул код {result.returncode}\n{result.stderr.strip()}"
            )

        return result.stdout

    def is_connected(self) -> bool:
        """Подключён ли телефон."""
        if shutil.which(self.executable) is None:
            return False

        lines = self.adb("devices", check=False).splitlines()[1:]
        return any(
            len(parts := line.split()) >= 2 and parts[1] == "device"
            for line in lines
        )

    def wait_for_device(self, timeout: float = 30.0) -> None:
        """Дождаться, пока телефон появится в adb."""
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if self.is_connected():
                return
            time.sleep(1.0)

        raise AdbError(f"телефон не появился за {timeout:.0f}с")

    # --- скриншоты и тапы --------------------------------------------------

    def capture(self, destination: str | Path) -> Path:
        """Снять скриншот телефона и сохранить локально.

        Скриншот пишется прямо на устройство в /sdcard, потому что доступа
        к /data у обычного приложения нет, а потом забирается через adb pull.
        """
        if not self.is_connected():
            raise AdbError("телефон не подключён")

        local = Path(destination)
        local.parent.mkdir(parents=True, exist_ok=True)

        self.adb("shell", "mkdir", "-p", self.device.device_dir)
        self.adb("shell", "screencap", "-p", self.device.device_file)
        self.adb("pull", self.device.device_file, str(local))
        self.adb("shell", "rm", "-f", self.device.device_file)

        if not local.exists() or local.stat().st_size == 0:
            raise AdbError(f"скриншот не получен: {local}")

        log.debug("снимок %s (%d байт)", local, local.stat().st_size)
        return local

    def tap(self, x: float, y: float) -> None:
        """Одиночный тап. В игре ставит крестик, поэтому сам по себе не нужен."""
        self.adb("shell", "input", "tap", str(int(x)), str(int(y)))

    def double_tap(self, x: float, y: float) -> None:
        """Двойной тап: ставит котика.

        Оба тапа уходят одной командой adb shell. Два отдельных вызова дают
        между тапами сотни миллисекунд на запуск adb, и игра такой тап
        двойным не считает.
        """
        column, row = str(int(x)), str(int(y))
        delay = self.timing.double_tap_delay

        self.adb(
            "shell",
            f"input motionevent DOWN {column} {row}; "
            f"input motionevent UP {column} {row}; "
            f"sleep {delay}; "
            f"input motionevent DOWN {column} {row}; "
            f"input motionevent UP {column} {row}",
        )
        time.sleep(self.timing.tap_settle)


# Короткие вызовы для скриптов и тестов, работают с телефоном по умолчанию.
_default_device = AdbDevice()


def adb(*args: str, check: bool = True) -> str:
    return _default_device.adb(*args, check=check)


def is_connected() -> bool:
    return _default_device.is_connected()


def capture(destination: str | Path) -> Path:
    return _default_device.capture(destination)


def tap(x: float, y: float) -> None:
    _default_device.tap(x, y)


def double_tap(x: float, y: float) -> None:
    _default_device.double_tap(x, y)


def wait_for_device(timeout: float = 30.0) -> None:
    _default_device.wait_for_device(timeout)
