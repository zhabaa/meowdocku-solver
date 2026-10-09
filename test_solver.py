"""Тесты солвера: сверка с перебором, случайные доски, найденные котики.

Запуск: .venv/bin/python test_solver.py
"""

import itertools
import random
import time
from pathlib import Path

from config import Settings
from domain import Cell
from field import read_board
from solver import Solver, UniqueSolutionRequired

IMG_DIR = Path(__file__).parent / "img" / "tmp"
SHOTS_DIR = Path(__file__).parent / "img" / "screenshots"

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def make_solver() -> Solver:
    return Solver(time_limit=Settings().timing.solve_time_limit)


def brute_force(colors, found_cats=()) -> list[tuple[Cell, ...]]:
    """Перебрать расстановки честным полным перебором перестановок.

    Медленно, зато максимально просто и независимо от солвера.
    """
    size = len(colors)
    found: list[tuple[Cell, ...]] = []
    known = {Cell(row, col) for row, col in found_cats}

    for columns in itertools.permutations(range(size)):
        # Кошки не касаются: в соседних строках столбцы расходятся больше чем на 1.
        if any(abs(columns[row] - columns[row + 1]) <= 1 for row in range(size - 1)):
            continue

        letters = [colors[row][columns[row]] for row in range(size)]
        if len(set(letters)) != size:
            continue

        cats = tuple(Cell(row, columns[row]) for row in range(size))
        if any(cat not in cats for cat in known):
            continue

        found.append(cats)

    return found


def test_matches_brute_force_on_real_screens() -> None:
    solver = make_solver()

    for name in ("TEST_SCREEN", "TEST_SCREEN8", "TEST_SCREEN9", "TEST_SCREEN10"):
        board = read_board(str(IMG_DIR / f"{name}.png"))

        found = brute_force(board.colors, board.cats)
        check(
            len(found) == 1,
            f"{name}: перебор нашёл {len(found)} решений, ожидалось ровно 1",
        )

        solution = solver.solve(board.colors, board.cats)
        check(
            solution.cats == found[0],
            f"{name}: солвер дал {solution}, перебор дал {found[0]}",
        )
        check(len(solution) == board.size, f"{name}: котиков {len(solution)}, ожидалось {board.size}")


def test_matches_brute_force_on_live_screens() -> None:
    """Поля, снятые с телефона."""
    solver = make_solver()

    for name in ("shot_3.jpg", "shot_5.jpg", "shot_6.jpg", "shot_8.jpg",
                 "live_10x10_empty.png", "live_9x9_cat_on_grey.png",
                 "live_10x10_one_cat.png"):
        board = read_board(str(SHOTS_DIR / name))

        found = brute_force(board.colors, board.cats)
        check(len(found) == 1, f"{name}: перебор нашёл {len(found)} решений, ожидалось 1")

        solution = solver.solve(board.colors, board.cats)
        check(
            solution.cats == found[0],
            f"{name}: солвер дал {solution}, перебор дал {found[0]}",
        )


def test_known_cats_do_not_change_answer() -> None:
    """Найденные котики не должны ломать решение, а должны подтверждаться им."""
    board = read_board(str(IMG_DIR / "TEST_SCREEN.png"))
    solver = make_solver()
    solution = solver.solve(board.colors, board.cats)

    check(len(board.cats) == 1, "TEST_SCREEN: ожидался один найденный котик")
    for cat in board.cats:
        check(Cell(*cat) in solution, f"найденный котик {cat} не попал в решение {solution}")

    # Подсовываем заведомо чужую клетку: солвер обязан споткнуться.
    wrong = next(
        Cell(row, col)
        for row in range(board.size)
        for col in range(board.size)
        if (Cell(row, col) not in solution and (row, col) not in board.cats)
    )
    try:
        solver.solve(board.colors, [wrong])
        failures.append(f"заведомо неверный котик {wrong} принят как решение")
    except UniqueSolutionRequired:
        pass


def test_contradictory_found_cats() -> None:
    board = read_board(str(IMG_DIR / "TEST_SCREEN.png"))
    solver = make_solver()

    # Две кошки одного цвета.
    letter = board.colors[0][0]
    same_color = [
        Cell(row, col)
        for row in range(board.size)
        for col in range(board.size)
        if board.colors[row][col] == letter
    ]
    try:
        solver.solve(board.colors, same_color[:2])
        failures.append("две кошки одного цвета приняты")
    except UniqueSolutionRequired:
        pass

    # Котик вне поля.
    try:
        solver.solve(board.colors, [Cell(board.size, 0)])
        failures.append("котик вне поля принят")
    except UniqueSolutionRequired:
        pass


def test_ambiguous_board_is_rejected() -> None:
    """Поле с несколькими решениями обязано быть отвергнуто, а не решено наугад."""
    colors = ["ADDB", "BDDB", "ACCA", "ACCA"]
    check(not make_solver().is_unique(colors), "поле с несколькими решениями прошло как уникальное")

    try:
        make_solver().solve(colors)
        failures.append("поле с несколькими решениями не отвергнуто")
    except UniqueSolutionRequired as error:
        check("неверно" in str(error), f"неожиданный текст ошибки: {error}")


def test_unsolvable_board_is_rejected() -> None:
    colors = ["AAAA", "BBBB", "CCCC", "DDDD"]
    check(not make_solver().is_unique(colors), "поле без решения прошло как уникальное")


def test_random_boards_against_brute_force() -> None:
    """Случайные доски: если решение единственное, солвер обязан его найти."""
    solver = make_solver()
    rng = random.Random(20261009)
    unique_count = 0
    ambiguous_count = 0

    for _ in range(400):
        size = rng.randint(4, 8)
        colors = [
            "".join(rng.choice("ABCDEFGH"[:size]) for _ in range(size)) for _ in range(size)
        ]

        found = brute_force(colors)
        unique = solver.is_unique(colors)

        check(
            unique == (len(found) == 1),
            f"n={size} {colors}: солвер считает уникальным={unique}, "
            f"перебор нашёл {len(found)}",
        )

        if unique:
            unique_count += 1
            solution = solver.solve(colors)
            check(
                solution.cats == found[0],
                f"n={size} {colors}: солвер {solution}, перебор {found[0]}",
            )
        elif len(found) > 1:
            ambiguous_count += 1

    print(f"  случайных досок: уникальных {unique_count}, многовариантных {ambiguous_count}")


def test_solution_respects_rules() -> None:
    """Расстановка обязана удовлетворять всем трём правилам игры."""
    solver = make_solver()

    for name in ("TEST_SCREEN8", "TEST_SCREEN9", "TEST_SCREEN10"):
        board = read_board(str(IMG_DIR / f"{name}.png"))
        solution = solver.solve(board.colors, board.cats)

        check(len({cat.row for cat in solution}) == board.size, f"{name}: не по одной кошке на строку")
        check(len({cat.col for cat in solution}) == board.size, f"{name}: не по одной кошке на столбец")
        check(
            len({board.colors[cat.row][cat.col] for cat in solution}) == board.size,
            f"{name}: не по одной кошке на цвет",
        )

        for first, second in itertools.combinations(solution, 2):
            touching = abs(first.row - second.row) <= 1 and abs(first.col - second.col) <= 1
            check(not touching, f"{name}: котики {first} и {second} касаются")


def test_speed_on_synthetic_large_board() -> None:
    """Большое поле должно считаться быстро, иначе цикл в игре подвиснет."""
    rng = random.Random(7)
    size = 12
    rows = ["".join(rng.choice("ABCDEFGHIJKL") for _ in range(size)) for _ in range(size)]

    start = time.monotonic()
    try:
        make_solver().solve(rows)
    except UniqueSolutionRequired:
        pass
    elapsed = time.monotonic() - start

    print(f"  поле {size}x{size}: {elapsed:.3f}с")
    check(elapsed < 5.0, f"поле {size}x{size} считалось {elapsed:.3f}с, слишком долго")


def test_accepts_cells_and_tuples() -> None:
    """Решение одинаково принимает Cell и пару (строка, столбец)."""
    colors = ["CBDC", "BAAD", "CCAA", "ADAC"]
    solver = make_solver()

    if not solver.is_unique(colors):
        failures.append("доска для проверки вдруг стала неоднозначной")
        return

    cat = solver.solve(colors).cats[0]
    as_tuples = solver.solve(colors, [(cat.row, cat.col)])
    as_cells = solver.solve(colors, [cat])

    check(as_tuples.cats == as_cells.cats, "Cell и пара дают разные решения")
    check(cat in as_cells, "котик из решения не подтвердился самим собой")


def main() -> int:
    for test in (
        test_matches_brute_force_on_real_screens,
        test_matches_brute_force_on_live_screens,
        test_known_cats_do_not_change_answer,
        test_contradictory_found_cats,
        test_ambiguous_board_is_rejected,
        test_unsolvable_board_is_rejected,
        test_solution_respects_rules,
        test_random_boards_against_brute_force,
        test_speed_on_synthetic_large_board,
        test_accepts_cells_and_tuples,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures[:20]:
            print(f"  - {message}")
        if len(failures) > 20:
            print(f"  ... и ещё {len(failures) - 20}")
        return 1

    print("\nВсе тесты солвера прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
