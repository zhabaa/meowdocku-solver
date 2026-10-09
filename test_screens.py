"""Тесты определения экрана на реальных скриншотах.

Запуск: .venv/bin/python test_screens.py
"""

from pathlib import Path

import cv2
import numpy as np

from field import Board
from screens import ScreenKind, detect, find_continue_hint, find_level_done_button

SHOTS = Path(__file__).parent / "img" / "screenshots"

# Что должно быть на каждом скрине.
EXPECTED = {
    1: ScreenKind.LEADERBOARD,
    2: ScreenKind.LEVEL_DONE,
    3: ScreenKind.BOARD,
    4: ScreenKind.LEADERBOARD,
    5: ScreenKind.BOARD,
    6: ScreenKind.BOARD,
    7: ScreenKind.LEVEL_DONE,
    8: ScreenKind.BOARD,
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def test_detects_all_screens() -> None:
    for number, expected in sorted(EXPECTED.items()):
        screen = detect(SHOTS / f"shot_{number}.jpg")
        check(
            screen.kind == expected,
            f"shot_{number}: определено как {screen.kind}, ожидалось {expected}",
        )


def test_board_screens_are_readable() -> None:
    expected_sizes = {3: 9, 5: 8, 6: 8, 8: 8}
    for number, n in sorted(expected_sizes.items()):
        screen = detect(SHOTS / f"shot_{number}.jpg")
        if screen.kind != ScreenKind.BOARD:
            failures.append(f"shot_{number}: ожидалось поле, а получено {screen.kind}")
            continue
        check(screen.board.n == n, f"shot_{number}: N = {screen.board.n}, ожидалось {n}")


def test_cats_match_manual_look() -> None:
    """Сколько котиков на поле — проверено глазами по скринам."""
    expected_cats = {3: 2, 5: 0, 6: 3, 8: 1}
    for number, count in sorted(expected_cats.items()):
        screen = detect(SHOTS / f"shot_{number}.jpg")
        if screen.kind != ScreenKind.BOARD:
            failures.append(f"shot_{number}: ожидалось поле")
            continue
        check(
            len(screen.board.cats) == count,
            f"shot_{number}: котиков {len(screen.board.cats)}, ожидалось {count}",
        )


def test_button_not_found_on_boards() -> None:
    """Кнопка не должна появляться на поле, иначе бот уйдёт не туда."""
    for number in (3, 5, 6, 8):
        image = cv2.imread(str(SHOTS / f"shot_{number}.jpg"))
        check(
            find_level_done_button(image) is None,
            f"shot_{number}: на поле нашлась кнопка пройденного уровня",
        )


def test_button_found_on_both_done_screens() -> None:
    """Кнопка бывает и «Золотая рыбка», и «Уровень 334» — обе ищутся."""
    for number in (2, 7):
        image = cv2.imread(str(SHOTS / f"shot_{number}.jpg"))
        point = find_level_done_button(image)
        check(point is not None, f"shot_{number}: кнопка не найдена")
        if point is None:
            continue

        height, width = image.shape[:2]
        check(
            0 < point[0] < width and 0 < point[1] < height,
            f"shot_{number}: кнопка {point} вне экрана {width}x{height}",
        )
        check(
            point[1] > height * 0.6,
            f"shot_{number}: кнопка {point} слишком высоко",
        )


def test_hint_only_on_leaderboards() -> None:
    for number in (1, 4):
        image = cv2.imread(str(SHOTS / f"shot_{number}.jpg"))
        check(
            find_continue_hint(image) is not None,
            f"shot_{number}: надпись не найдена",
        )

    for number in (3, 5, 6, 8):
        image = cv2.imread(str(SHOTS / f"shot_{number}.jpg"))
        check(
            find_continue_hint(image) is None,
            f"shot_{number}: на поле нашлась надпись для лидеров",
        )


def test_blank_screen_is_unknown() -> None:
    """Пустой экран не должен превращаться ни в поле, ни в кнопку."""
    blank = SHOTS / "BLANK.png"
    image = np.full((2340, 1080, 3), 250, dtype=np.uint8)
    cv2.imwrite(str(blank), image)

    try:
        screen = detect(blank)
        check(
            screen.kind == ScreenKind.UNKNOWN,
            f"пустой экран определён как {screen.kind}, ожидалось unknown",
        )
    finally:
        blank.unlink(missing_ok=True)


def test_missing_file_raises() -> None:
    try:
        detect(SHOTS / "NO_SUCH_SHOT.png")
        failures.append("отсутствующий файл не поднял ошибку")
    except FileNotFoundError:
        pass


def main() -> int:
    for test in (
        test_detects_all_screens,
        test_board_screens_are_readable,
        test_cats_match_manual_look,
        test_button_not_found_on_boards,
        test_button_found_on_both_done_screens,
        test_hint_only_on_leaderboards,
        test_blank_screen_is_unknown,
        test_missing_file_raises,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты определения экрана прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())