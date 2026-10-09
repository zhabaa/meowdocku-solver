"""Тесты чтения поля на реальных скриншотах и на синтетической картинке.

Запуск: .venv/bin/python test_field.py
"""

from pathlib import Path

import cv2
import numpy as np

from field import BoardReadError, read_board

IMG_DIR = Path(__file__).parent / "img" / "tmp"
SHOTS_DIR = Path(__file__).parent / "img" / "screenshots"

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


def test_grey_cat_cell() -> None:
    """Котик с серой мордой не попадает в маску насыщенности.

    Такая клетка распадается на мелкие куски и в списке клеток её нет. Без
    достраивания сетки поле 9x9 читалось как 8 строк с одной дыркой, и бот
    падал сразу после постановки первого котика.
    """
    path = SHOTS_DIR / "live_9x9_cat_on_grey.png"
    board = read_board(str(path))

    check(board.n == 9, f"поле {board.n}x{board.n}, ожидалось 9x9")
    check(
        set(board.cats) == {(7, 6)},
        f"котики {sorted(board.cats)}, ожидался только (7,6)",
    )

    from solver import solve_from_board

    solution = solve_from_board(board)
    check((7, 6) in solution, f"котик (7,6) не попал в решение {solution}")
    check(len(solution) == 9, f"в решении {len(solution)} кошек, ожидалось 9")


def test_live_screens() -> None:
    """Скриншоты с настоящего телефона: 10x10, один с найденным котом.

    Отдельно важный случай: после постановки котика рядом со счётом очков
    появляется блик размером 70x70, и при прежнем допуске 0.3 он проходил
    как клетка — поле читалось как 11 строк вместо 10.
    """
    empty = SHOTS_DIR / "live_10x10_empty.png"
    with_cat = SHOTS_DIR / "live_10x10_one_cat.png"

    board = read_board(str(empty))
    check(board.n == 10, f"поле {board.n}x{board.n}, ожидалось 10x10")
    check(board.cats == frozenset(), f"на пустом поле котики {sorted(board.cats)}")

    board = read_board(str(with_cat))
    check(board.n == 10, f"поле {board.n}x{board.n} после тапа, ожидалось 10x10")
    check(
        set(board.cats) == {(0, 4)},
        f"после тапа котики {sorted(board.cats)}, ожидался только (0,4)",
    )

    # Раскладка не должна поехать от того, что в клетке кто-то есть.
    from solver import solve_from_board

    solution = solve_from_board(board)
    check(
        (0, 4) in solution,
        f"котик (0,4) не попал в решение {solution}",
    )
    check(
        len([c for c in solution if c not in board.cats]) == 9,
        "после одного тапа осталось не 9 кошек",
    )


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
    for test in (
        test_real_screens,
        test_live_screens,
        test_grey_cat_cell,
        test_synthetic_board,
        test_bad_input,
    ):
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