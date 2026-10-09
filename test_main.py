"""Тесты игрового цикла: телефон подменён, поле читается из файлов.

Проверяем главное: бот тапает только найденные решения, не тапает повторно
уже найденных кошек и останавливается, если поле прочиталось неверно.

Запуск: .venv/bin/python test_main.py
"""

import shutil
from pathlib import Path
from unittest import mock

import main
from field import BoardReadError, read_board
from solver import InconsistentBoard, solve_from_board

TMP = Path(__file__).parent / "img" / "tmp"

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


class FakePhone:
    """Телефон, который только делает скриншоты и запоминает тапы."""

    def __init__(self, images: list[Path]):
        self.images = list(images)
        self.taps: list[tuple[int, int]] = []
        self.shots = 0

    def capture(self, destination) -> Path:
        local = Path(destination)
        local.parent.mkdir(parents=True, exist_ok=True)

        source = self.images[min(self.shots, len(self.images) - 1)]
        shutil.copyfile(source, local)
        self.shots += 1
        return local

    def double_tap(self, x, y) -> None:
        self.taps.append((int(x), int(y)))


def test_taps_exactly_the_planned_cats() -> None:
    phone = FakePhone([TMP / "TEST_SCREEN8.png"])

    # Ожидаемые тапы берём из самого поля: так тест проверяет цикл,
    # а не захардкоженные пиксели.
    board = read_board(str(TMP / "TEST_SCREEN8.png"))
    solution = solve_from_board(board)
    expected = {tuple(map(int, board.tap_point(r, c))) for r, c in solution}

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"):
        code = main.play(dry_run=False)

    check(code == 0, f"вернулся код {code}, ожидался 0")
    check(len(phone.taps) == 8, f"тапов {len(phone.taps)}, ожидалось 8")
    check(set(phone.taps) == expected, f"тапы не совпали: {sorted(phone.taps)}")


def test_dry_run_never_taps() -> None:
    phone = FakePhone([TMP / "TEST_SCREEN.png"])

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"):
        code = main.play(dry_run=True)

    check(code == 0, f"вернулся код {code}, ожидался 0")
    check(not phone.taps, f"в dry-run было {len(phone.taps)} тапов, ожидался ноль")


def test_found_cat_is_not_tapped_again() -> None:
    """Найденный котик повторно не тапаем: это тратит жизнь."""
    phone = FakePhone([TMP / "TEST_SCREEN.png"])

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"):
        main.play(dry_run=False)

    check(len(phone.taps) == 7, f"тапов {len(phone.taps)}, ожидалось 7 (8 котов минус найденный)")
    check((983, 1145) not in phone.taps, "тапали в клетку с уже найденным котиком")


def test_stops_when_board_is_unreadable() -> None:
    """Если поле не прочиталось, бот не должен ничем тапать.

    Например, уровень пройден и вместо поля на экране другой экран.
    """
    phone = FakePhone([TMP / "TEST_SCREEN8.png"])

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"), \
         mock.patch.object(
             main, "read_board", side_effect=BoardReadError("поле не найдено")
         ):
        code = main.play(dry_run=False)

    check(code == 1, f"вернулся код {code}, ожидался 1")
    check(not phone.taps, "тапали, хотя поле не прочиталось")


def test_unexpected_error_is_not_swallowed() -> None:
    """Неожиданную ошибку глотать нельзя: пусть лучше упадёт с traceback."""
    phone = FakePhone([TMP / "TEST_SCREEN8.png"])

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"), \
         mock.patch.object(main, "read_board", side_effect=MemoryError()):
        try:
            main.play(dry_run=False)
            failures.append("MemoryError проглочен, а должен был упасть")
        except MemoryError:
            pass

    check(not phone.taps, "тапали, хотя чтение поля упало с неожиданной ошибкой")


def test_stops_on_ambiguous_board() -> None:
    """Неоднозначное поле — тоже не тапаем, а падаем."""
    phone = FakePhone([TMP / "TEST_SCREEN8.png"])

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=phone.capture), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"), \
         mock.patch.object(
             main, "solve_from_board",
             side_effect=InconsistentBoard("Решений минимум 2"),
         ):
        code = main.play(dry_run=False)

    check(code == 1, f"вернулся код {code}, ожидался 1")
    check(not phone.taps, "тапали на неоднозначном поле")


def test_survives_field_disappearing_midway() -> None:
    """Если во время игры поле пропало (уровень пройден), не падаем."""
    board_image = TMP / "TEST_SCREEN8.png"
    gone_image = TMP / "GONE.png"
    shutil.copyfile(board_image, gone_image)

    phone = FakePhone([board_image, gone_image])

    def capture(destination):
        local = Path(destination)
        local.parent.mkdir(parents=True, exist_ok=True)
        index = min(phone.shots, len(phone.images) - 1)
        source = phone.images[index]
        # После первого тапа поле исчезает.
        if phone.shots > 1:
            source = gone_image
        shutil.copyfile(source, local)
        phone.shots += 1
        return local

    gone = TMP / "NOT_A_BOARD.png"
    gone.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    def capture_with_disappearance(destination):
        result = capture(destination)
        if phone.shots > 2:
            shutil.copyfile(gone, result)
        return result

    with mock.patch.object(main, "OUT_DIR", TMP), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch.object(main.emulate, "capture", side_effect=capture_with_disappearance), \
         mock.patch.object(main.emulate, "double_tap", side_effect=phone.double_tap), \
         mock.patch.object(main.time, "sleep"):
        code = main.play(dry_run=False)

    check(code == 0, f"вернулся код {code}, ожидался 0")
    check(len(phone.taps) < 8, f"сделано {len(phone.taps)} тапов, цикл не прервался")

    gone.unlink(missing_ok=True)


def test_run_on_image() -> None:
    code = main.run_on_image(TMP / "TEST_SCREEN9.png")
    check(code == 0, f"вернулся код {code}")
    check((TMP / "preview.png").exists(), "preview.png не создан")

    code = main.run_on_image(TMP / "MISSING.png")
    check(code == 1, f"для отсутствующего файла вернулся {code}, ожидался 1")


def main_run() -> int:
    tests = (
        test_taps_exactly_the_planned_cats,
        test_dry_run_never_taps,
        test_found_cat_is_not_tapped_again,
        test_stops_when_board_is_unreadable,
        test_unexpected_error_is_not_swallowed,
        test_stops_on_ambiguous_board,
        test_survives_field_disappearing_midway,
        test_run_on_image,
    )

    for test in tests:
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты игрового цикла прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_run())