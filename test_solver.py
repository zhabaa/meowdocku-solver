"""Тесты солвера: сверка с перебором, случайные доски, найденные котики.

Запуск: .venv/bin/python test_solver.py
"""

import itertools
import random
import time
from pathlib import Path

from field import read_board
from solver import InconsistentBoard, is_unique, solve, solve_from_board

IMG_DIR = Path(__file__).parent / "img" / "tmp"

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def brute_force(colors, found_cats=()) -> list[tuple[tuple[int, int], ...]]:
    """Перебрать расстановки честным полным перебором перестановок.

    Медленно, зато максимально просто и независимо от солвера.
    """
    n = len(colors)
    found: list[tuple[tuple[int, int], ...]] = []

    for cols in itertools.permutations(range(n)):
        # Кошки не касаются: в соседних строках столбцы расходятся больше чем на 1.
        if any(abs(cols[i] - cols[i + 1]) <= 1 for i in range(n - 1)):
            continue

        letters = [colors[row][cols[row]] for row in range(n)]
        if len(set(letters)) != n:
            continue

        if any(cols[row] != col for row, col in set(found_cats)):
            continue

        found.append(tuple((row, cols[row]) for row in range(n)))

    return found


def test_matches_brute_force_on_real_screens() -> None:
    for name in ("TEST_SCREEN", "TEST_SCREEN8", "TEST_SCREEN9", "TEST_SCREEN10"):
        board = read_board(str(IMG_DIR / f"{name}.png"))

        found = brute_force(board.colors)
        check(
            len(found) == 1,
            f"{name}: перебор нашёл {len(found)} решений, ожидалось ровно 1",
        )

        solution = solve_from_board(board)
        check(
            solution.cats == found[0],
            f"{name}: солвер дал {solution}, перебор дал {found[0]}",
        )
        check(len(solution) == board.n, f"{name}: котиков {len(solution)}, ожидалось {board.n}")


def test_known_cats_do_not_change_answer() -> None:
    """Найденные котики не должны ломать решение, а должны подтверждаться им."""
    board = read_board(str(IMG_DIR / "TEST_SCREEN.png"))
    solution = solve_from_board(board)

    check(len(board.cats) == 1, "TEST_SCREEN: ожидался один найденный котик")

    for cat in board.cats:
        check(cat in solution, f"найденный котик {cat} не попал в решение {solution}")

    # Подсовываем заведомо чужую клетку: солвер обязан споткнуться.
    wrong = next(
        (row, col)
        for row in range(board.n)
        for col in range(board.n)
        if (row, col) not in solution and (row, col) not in board.cats
    )
    try:
        solve(board.colors, [wrong])
        failures.append(f"заведомо неверный котик {wrong} принят как решение")
    except InconsistentBoard:
        pass


def test_contradictory_found_cats() -> None:
    board = read_board(str(IMG_DIR / "TEST_SCREEN.png"))
    solution = solve_from_board(board)

    # Две кошки одного цвета.
    color = board.colors[0][0]
    same_color = [
        (r, c)
        for r in range(board.n)
        for c in range(board.n)
        if board.colors[r][c] == color
    ]
    try:
        solve(board.colors, same_color[:2])
        failures.append("две кошки одного цвета приняты")
    except InconsistentBoard:
        pass

    # Котик вне поля.
    try:
        solve(board.colors, [(board.n, 0)])
        failures.append("котик вне поля принят")
    except InconsistentBoard:
        pass


def test_ambiguous_board_is_rejected() -> None:
    """Поле с несколькими решениями обязано быть отвергнуто, а не решено наугад."""
    colors = ["ADDB", "BDDB", "ACCA", "ACCA"]
    check(not is_unique(colors), "поле с несколькими решениями прошло как уникальное")

    try:
        solve(colors)
        failures.append("поле с несколькими решениями не отвергнуто")
    except InconsistentBoard as error:
        check("неверно" in str(error), f"неожиданный текст ошибки: {error}")


def test_unsolvable_board_is_rejected() -> None:
    colors = ["AAAA", "BBBB", "CCCC", "DDDD"]
    check(not is_unique(colors), "поле без решения прошло как уникальное")


def test_random_boards_against_brute_force() -> None:
    """Случайные доски: если решение единственное, солвер обязан его найти."""
    rng = random.Random(20261009)
    checked_unique = 0
    checked_ambiguous = 0

    for _ in range(400):
        n = rng.randint(4, 8)
        colors = [
            "".join(rng.choice("ABCDEFGH"[:n]) for _ in range(n)) for _ in range(n)
        ]

        found = brute_force(colors)
        unique = is_unique(colors)

        check(
            unique == (len(found) == 1),
            f"n={n} {colors}: солвер считает уникальным={unique}, "
            f"перебор нашёл {len(found)}",
        )

        if unique:
            checked_unique += 1
            solution = solve(colors)
            check(
                solution.cats == found[0],
                f"n={n} {colors}: солвер {solution}, перебор {found[0]}",
            )
        elif len(found) > 1:
            checked_ambiguous += 1

    print(
        f"  случайных досок: уникальных {checked_unique}, "
        f"многовариантных {checked_ambiguous}"
    )


def test_solution_respects_rules() -> None:
    """Расстановка обязана удовлетворять всем трём правилам игры."""
    for name in ("TEST_SCREEN8", "TEST_SCREEN9", "TEST_SCREEN10"):
        board = read_board(str(IMG_DIR / f"{name}.png"))
        solution = solve_from_board(board)
        n = board.n

        rows = [r for r, _ in solution]
        cols = [c for _, c in solution]
        letters = [board.colors[r][c] for r, c in solution]

        check(len(set(rows)) == n, f"{name}: не по одной кошке на строку")
        check(len(set(cols)) == n, f"{name}: не по одной кошке на столбец")
        check(len(set(letters)) == n, f"{name}: не по одной кошке на цвет")

        for (r1, c1), (r2, c2) in itertools.combinations(solution, 2):
            touching = abs(r1 - r2) <= 1 and abs(c1 - c2) <= 1
            check(not touching, f"{name}: котики {(r1, c1)} и {(r2, c2)} касаются")


def test_speed_on_synthetic_large_board() -> None:
    """Большое поле должно считаться быстро, иначе цикл в игре подвиснет."""
    rng = random.Random(7)
    n = 12
    rows = []
    for _ in range(n):
        rows.append("".join(rng.choice("ABCDEFGHIJKL") for _ in range(n)))

    start = time.monotonic()
    try:
        solve(rows, time_limit=30.0)
    except InconsistentBoard:
        pass
    elapsed = time.monotonic() - start

    print(f"  поле {n}x{n}: {elapsed:.3f}s")
    check(elapsed < 5.0, f"поле {n}x{n} считалось {elapsed:.3f}s, слишком долго")


def main() -> int:
    tests = (
        test_matches_brute_force_on_real_screens,
        test_known_cats_do_not_change_answer,
        test_contradictory_found_cats,
        test_ambiguous_board_is_rejected,
        test_unsolvable_board_is_rejected,
        test_solution_respects_rules,
        test_random_boards_against_brute_force,
        test_speed_on_synthetic_large_board,
    )

    for test in tests:
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