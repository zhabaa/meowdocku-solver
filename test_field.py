"""Тесты чтения поля на реальных скриншотах и на синтетической картинке.

Запуск: .venv/bin/python test_field.py
"""

from pathlib import Path

import cv2
import numpy as np

from field import BoardReadError, read_board

IMG_DIR = Path(__file__).parent / "img" / "tmp"

# Что ожидаем увидеть на каждом реальном скриншоте.
EXPECTED = {
    "TEST_SCREEN": (8, {(3, 7)}),
    "TEST_SCREEN8": (8, set()),
    "TEST_SCREEN9": (9, set()),
    "TEST_SCREEN10": (10, set()),
}

# Эталонные поля, сверенные глазами со скриншотов.
EXPECTED_COLORS = {
    "TEST_SCREEN": (
        "AAAAAABB",
        "ACCCCCCB",
        "ACCDCBBB",
        "ACDDDEBF",
        "CCCDDEBB",
        "CGDDEEBH",
        "CGDDEEBH",
        "CGGDDDHH",
    ),
    "TEST_SCREEN8": (
        "AAAAAABB",
        "ACCCCCCB",
        "ACCDCBBB",
        "ACDDDEBF",
        "CCCDDEBB",
        "CGDDEEBH",
        "CGDDEEBH",
        "CGGDDDHH",
    ),
    "TEST_SCREEN9": (
        "AAABBBBCC",
        "AAADBBBBC",
        "AEABBEEEC",
        "AEEEEECCC",
        "AEFEGEGGH",
        "AFFGGEEGH",
        "AAFFGGEGH",
        "AIIIAGGGH",
        "AAAAAAAGG",
    ),
    "TEST_SCREEN10": (
        "AAAAAABBBB",
        "CCCCCAADBB",
        "CEFFCAADDD",
        "CEFFCAAGDD",
        "CEFFFHAGGI",
        "CEFHHHHIII",
        "CEFFFFHIII",
        "CEEFHHHHHH",
        "CJJJHJJJJH",
        "CJJJJJJJJH",
    ),
}

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def test_real_screens() -> None:
    for name, (n, cats) in EXPECTED.items():
        path = IMG_DIR / f"{name}.png"
        if not path.exists():
            failures.append(f"{name}: скриншот не найден по пути {path}")
            continue

        board = read_board(str(path))

        check(board.n == n, f"{name}: N = {board.n}, ожидалось {n}")
        check(
            set(board.cats) == cats,
            f"{name}: котики {sorted(board.cats)}, ожидалось {sorted(cats)}",
        )
        check(
            len(board.palette) == n,
            f"{name}: в палитре {len(board.palette)} цветов, ожидалось {n}",
        )
        actual = tuple("".join(row) for row in board.colors)
        check(
            actual == EXPECTED_COLORS[name],
            f"{name}: поле прочитано неверно\nожидалось:\n"
            + "\n".join(EXPECTED_COLORS[name])
            + f"\nполучено:\n{board}",
        )

        # Каждая клетка имеет свой тап, и он внутри своей клетки.
        check(
            len(board.tap_points) == n * n,
            f"{name}: тап-точек {len(board.tap_points)}, ожидалось {n * n}",
        )
        for row in range(n):
            for col in range(n):
                tap_x, tap_y = board.tap_point(row, col)
                cx, cy = board.centers[row * n + col]
                check(
                    abs(tap_x - cx) < 20 and abs(tap_y - cy) < 20,
                    f"{name}: тап ({row},{col}) слишком далеко от центра клетки",
                )


def test_synthetic_board() -> None:
    """Поле, нарисованное программно, должно читаться без ошибок."""
    n = 7
    cell = 80
    gap = 6
    origin_x, origin_y = 40, 40

    colors_bgr = [
        (200, 120, 120),
        (120, 200, 120),
        (120, 120, 200),
        (200, 200, 120),
        (120, 200, 200),
        (200, 120, 200),
        (200, 170, 90),
    ]

    size = origin_x * 2 + n * (cell + gap)
    image = np.full((size, size, 3), 250, dtype=np.uint8)

    for row in range(n):
        for col in range(n):
            x = origin_x + col * (cell + gap)
            y = origin_y + row * (cell + gap)
            image[y : y + cell, x : x + cell] = colors_bgr[(row + col) % n]

    path = IMG_DIR / "SYNTHETIC.png"
    cv2.imwrite(str(path), image)

    try:
        board = read_board(str(path))
        check(board.n == n, f"синтетика: N = {board.n}, ожидалось {n}")
        check(
            len(board.palette) == n,
            f"синтетика: в палитре {len(board.palette)} цветов, ожидалось {n}",
        )
        check(
            board.cats == frozenset(),
            f"синтетика: найдены котики {sorted(board.cats)}, их быть не должно",
        )
    finally:
        path.unlink(missing_ok=True)


def test_bad_input() -> None:
    """Пустой фон и битая картинка обязаны падать, а не молча читаться."""
    blank = IMG_DIR / "BLANK.png"
    image = np.full((800, 800, 3), 250, dtype=np.uint8)
    cv2.imwrite(str(blank), image)
    try:
        try:
            read_board(str(blank))
            failures.append("пустой фон: ожидалась ошибка BoardReadError")
        except BoardReadError:
            pass
    finally:
        blank.unlink(missing_ok=True)

    try:
        read_board(str(IMG_DIR / "NO_SUCH_FILE.png"))
        failures.append("битый путь: ожидалась ошибка BoardReadError")
    except BoardReadError:
        pass


def main() -> int:
    for test in (test_real_screens, test_synthetic_board, test_bad_input):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты чтения поля прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())