"""Тесты чтения поля на реальных скриншотах и на синтетической картинке.

Запуск: .venv/bin/python test_field.py
"""

from pathlib import Path
import random

import cv2
import numpy as np

from meowdoku_bot.domain import Cell
from meowdoku_bot.field import BoardReadError, BoardReader, read_board

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


def test_cross_is_not_a_cat() -> None:
    """Белый крестик не должен читаться как котик.

    Крестик оставляется одиночным тапом, и раньше он попадал в список
    котиков: 53% его пикселей отличаются от цвета клетки, этого хватало
    старому порогу. Различает их тёмная морда котика — у крестика нет ни
    одного пикселя темнее 140.
    """
    board = read_board(str(SHOTS_DIR / "live_10x10_yellow_field.png"))

    check(board.size == 10, f"поле {board.size}x{board.size}, ожидалось 10x10")
    check(
        board.cats == frozenset(),
        f"крестик прочитан как котики {sorted(board.cats)}, поле должно быть пустым",
    )

    # Поле с крестиком как котиком не имеет решения, и проверка доски
    # отклонила бы его: с этим тест покрыт в test_loop.
    check(board.cats == frozenset(), "крестик снова попал в котики")


def test_cats_still_found_on_all_screens() -> None:
    """Ужесточение детектора не должно потерять настоящих котиков."""
    cases = {
        "shot_3.jpg": {(5, 3), (7, 4)},
        "shot_6.jpg": {(4, 3), (5, 5), (6, 0)},
        "shot_8.jpg": {(0, 1)},
        "live_9x9_cat_on_grey.png": {(7, 6)},
        "live_10x10_one_cat.png": {(0, 4)},
        "live_10x10_empty.png": set(),
        "live_10x10_light.png": set(),
    }

    for name, expected in cases.items():
        board = read_board(str(SHOTS_DIR / name))
        check(
            set(board.cats) == expected,
            f"{name}: котики {sorted(board.cats)}, ожидалось {sorted(expected)}",
        )


def test_grey_cat_cell() -> None:
    """Котик с серой мордой не попадает в маску насыщенности.

    Такая клетка распадается на мелкие куски и в списке клеток её нет. Без
    достраивания сетки поле 9x9 читалось как 8 строк с одной дыркой, и бот
    падал сразу после постановки первого котика.
    """
    path = SHOTS_DIR / "live_9x9_cat_on_grey.png"
    board = read_board(str(path))

    check(board.size == 9, f"поле {board.size}x{board.size}, ожидалось 9x9")
    check(
        set(board.cats) == {(7, 6)},
        f"котики {sorted(board.cats)}, ожидался только (7,6)",
    )

    from meowdoku_bot.solver import solve_from_board

    solution = solve_from_board(board)
    check(Cell(7, 6) in solution, f"котик (7,6) не попал в решение {solution}")
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
    check(board.size == 10, f"поле {board.size}x{board.size}, ожидалось 10x10")
    check(board.cats == frozenset(), f"на пустом поле котики {sorted(board.cats)}")

    board = read_board(str(with_cat))
    check(board.size == 10, f"поле {board.size}x{board.size} после тапа, ожидалось 10x10")
    check(
        set(board.cats) == {(0, 4)},
        f"после тапа котики {sorted(board.cats)}, ожидался только (0,4)",
    )

    # Раскладка не должна поехать от того, что в клетке кто-то есть.
    from meowdoku_bot.solver import solve_from_board

    solution = solve_from_board(board)
    board_cells = [Cell(row, col) for row, col in board.cats]
    check(
        Cell(0, 4) in solution,
        f"котик (0,4) не попал в решение {solution}",
    )
    check(
        len([cat for cat in solution if cat not in board_cells]) == 9,
        "после одного тапа осталось не 9 кошек",
    )


def test_real_screens() -> None:
    for name, (n, cats) in EXPECTED.items():
        path = IMG_DIR / f"{name}.png"
        if not path.exists():
            failures.append(f"{name}: скриншот не найден по пути {path}")
            continue

        board = read_board(str(path))

        check(board.size == n, f"{name}: N = {board.size}, ожидалось {n}")
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


def _connected_regions(n: int, count: int, seed: int) -> list[list[int]]:
    """Разбить поле на пятна, связанные по сторонам, — как в настоящей игре.

    Новое пятно всегда начинается рядом с уже покрашенной клеткой, поэтому
    каждый цвет остаётся одной связной областью.
    """
    rng = random.Random(seed)
    grid = [[-1] * n for _ in range(n)]
    steps = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def free_neighbors(row: int, col: int):
        for dr, dc in steps:
            other = (row + dr, col + dc)
            if 0 <= other[0] < n and 0 <= other[1] < n and grid[other[0]][other[1]] != -1:
                yield other

    for color in range(count):
        borders = [
            (row, col)
            for row in range(n)
            for col in range(n)
            if grid[row][col] == -1 and any(free_neighbors(row, col))
        ]
        empty = [
            (row, col) for row in range(n) for col in range(n) if grid[row][col] == -1
        ]
        start = rng.choice(borders or empty)
        grid[start[0]][start[1]] = color

        frontier = [start]
        while frontier:
            row, col = frontier.pop()
            fresh = [cell for cell in free_neighbors(row, col) if grid[cell[0]][cell[1]] == -1]
            if fresh:
                cell = rng.choice(fresh)
                grid[cell[0]][cell[1]] = color
                frontier.append(cell)

    # Оставшиеся клетки примыкают к пятнам, иначе сетка была бы несвязной.
    while any(value == -1 for row in grid for value in row):
        row, col = next(
            (r, c) for r in range(n) for c in range(n) if grid[r][c] == -1 and list(free_neighbors(r, c))
        )
        grid[row][col] = grid[next(free_neighbors(row, col))[0]][next(free_neighbors(row, col))[1]]

    return grid


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
    regions = _connected_regions(n, n, seed=20261009)

    for row in range(n):
        for col in range(n):
            x = origin_x + col * (cell + gap)
            y = origin_y + row * (cell + gap)
            image[y : y + cell, x : x + cell] = colors_bgr[regions[row][col]]

    path = IMG_DIR / "SYNTHETIC.png"
    cv2.imwrite(str(path), image)

    try:
        board = read_board(str(path))
        check(board.size == n, f"синтетика: N = {board.size}, ожидалось {n}")
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


def test_color_must_be_one_connected_region() -> None:
    """Цвет — это одно пятно, связанное по сторонам, а не по диагоналям.

    Правило игры: клетки одного цвета всегда соприкасаются боками. Если два
    пятна одного цвета не соединены, значит палитра прочитана неверно —
    тапать нельзя.
    """
    check_region = BoardReader._check_regions_contiguous

    # Пятно цельное — проходит.
    try:
        check_region(3, ("AAA", "AAA", "AAB"))
        check(True, "")
    except BoardReadError as error:
        failures.append(f"цельное пятно отвергнуто: {error}")

    # Тот же цвет по диагонали — пятна не соединены, поле отвергаем.
    try:
        check_region(2, ("AB", "BA"))
        failures.append("цвет, сошедшийся только по диагонали, не отвергнут")
    except BoardReadError as error:
        check("распался" in str(error), f"неожиданный текст ошибки: {error}")

    # Два раздельных пятна одного цвета — тоже отвергаем.
    try:
        check_region(3, ("ABA", "BBB", "ABA"))
        failures.append("разорванное на пятна пятно не отвергнуто")
    except BoardReadError as error:
        check("распался" in str(error), f"неожиданный текст ошибки: {error}")


def main() -> int:
    for test in (
        test_real_screens,
        test_live_screens,
        test_cross_is_not_a_cat,
        test_cats_still_found_on_all_screens,
        test_grey_cat_cell,
        test_synthetic_board,
        test_bad_input,
        test_color_must_be_one_connected_region,
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