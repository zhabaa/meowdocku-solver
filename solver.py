"""Поиск расстановки кошек на поле Meowdoku.

Правила:
  - ровно одна кошка в строке, в столбце и в каждом цвете,
  - кошки не касаются, даже по диагонали.

Игра генерирует поля с единственным решением, поэтому ищем ровно до
второго решения: нашли второе — значит поле прочитано неверно и тапать
нельзя.
"""

import time
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional, Sequence

# Столько решений достаточно, чтобы понять: решение единственное или нет.
AMBIGUOUS_AT = 2


class InconsistentBoard(RuntimeError):
    """Поле не имеет решения, либо найденные котики ему противоречат.

    Обычно значит, что цвета прочитаны неверно.
    """


@dataclass(frozen=True)
class Solution:
    n: int
    cats: tuple[tuple[int, int], ...]

    def __contains__(self, cell: tuple[int, int]) -> bool:
        return cell in self.cats

    def __iter__(self) -> Iterator[tuple[int, int]]:
        return iter(self.cats)

    def __len__(self) -> int:
        return len(self.cats)

    def __str__(self) -> str:
        return "котики: " + ", ".join(f"({r},{c})" for r, c in self.cats)


def solve(
    colors: Sequence[Sequence[str]],
    found_cats: Iterable[tuple[int, int]] = (),
    time_limit: float = 30.0,
) -> Solution:
    """Найти единственную расстановку кошек.

    Бросает InconsistentBoard, если решений нет или их больше одной.
    Поля без решения в игре не бывает, так что исключение — это сигнал
    ошибки чтения, а не штатная ситуация.
    """
    n = len(colors)
    if n == 0:
        raise InconsistentBoard("Поле пустое")
    if any(len(row) != n for row in colors):
        raise InconsistentBoard("Поле не квадратное")

    known = _validate_found(colors, n, found_cats)

    placements = _enumerate(colors, n, known, time_limit)

    if not placements:
        detail = "" if not known else f" с учётом найденных кошек {sorted(known)}"
        raise InconsistentBoard(f"Решений нет{detail}")

    if len(placements) >= AMBIGUOUS_AT:
        raise InconsistentBoard(
            f"Решений минимум {len(placements)} — поле прочитано неверно, тапать нельзя"
        )

    placement = placements[0]
    cats = tuple((row, col) for row, col in enumerate(placement))
    return Solution(n=n, cats=cats)


def is_unique(
    colors: Sequence[Sequence[str]],
    found_cats: Iterable[tuple[int, int]] = (),
    time_limit: float = 30.0,
) -> bool:
    """Единственное ли решение."""
    try:
        solve(colors, found_cats, time_limit)
    except InconsistentBoard:
        return False
    return True


def _validate_found(
    colors: Sequence[Sequence[str]],
    n: int,
    found_cats: Iterable[tuple[int, int]],
) -> dict[tuple[int, int], str]:
    """Проверить найденных кошек на вменяемость.

    Кошка занимает строку, столбец и цвет. Две кошки в одной строке или
    одного цвета означают, что поле прочитано неверно.
    """
    seen: dict[tuple[int, int], str] = {}
    rows: set[int] = set()
    cols: set[int] = set()
    letters: set[str] = set()

    for row, col in sorted(set(found_cats)):
        if not (0 <= row < n and 0 <= col < n):
            raise InconsistentBoard(f"Котик ({row},{col}) вне поля {n}x{n}")

        if row in rows:
            raise InconsistentBoard(f"Котики ({row},{col}) и ещё один делят строку {row}")
        if col in cols:
            raise InconsistentBoard(f"Котики ({row},{col}) и ещё один делят столбец {col}")

        letter = colors[row][col]
        if letter in letters:
            raise InconsistentBoard(f"Котик ({row},{col}) занимает цвет {letter}, уже занятый")

        rows.add(row)
        cols.add(col)
        letters.add(letter)
        seen[(row, col)] = letter

    return seen


def _enumerate(
    colors: Sequence[Sequence[str]],
    n: int,
    known: dict[tuple[int, int], str],
    time_limit: float,
) -> list[list[Optional[int]]]:
    """Перебрать расстановки обходом в глубину по строкам.

    В строке кошка одна, поэтому на каждом шаге выбираем столбец. Отсекаем
    ветки, где столбец занят, рядом стоит кошка или цвет уже использован.
    Возвращает не больше AMBIGUOUS_AT расстановок: двух достаточно, чтобы
    признать поле неоднозначным.
    """
    deadline = time.monotonic() + time_limit
    found: list[list[Optional[int]]] = []

    cols = list(range(n))
    placement: list[Optional[int]] = [None] * n
    # Столбец -> строка, чтобы проверка занятости была O(1).
    by_col: dict[int, int] = {}
    used_letters: set[str] = set()

    # Найденные котики ставим сразу: их позиции не выбираются.
    for (row, col), letter in known.items():
        placement[row] = col
        by_col[col] = row
        used_letters.add(letter)

    locked_rows = {row for row, _ in known}

    def search(row: int) -> None:
        if len(found) >= AMBIGUOUS_AT or time.monotonic() > deadline:
            return

        if row == n:
            found.append(placement[:])
            return

        if row in locked_rows:
            search(row + 1)
            return

        # Кошка выше по соседней строке, если она там есть.
        previous = placement[row - 1] if row > 0 else None

        for col in cols:
            if col in by_col:
                continue
            if previous is not None and abs(col - previous) <= 1:
                continue
            letter = colors[row][col]
            if letter in used_letters:
                continue

            placement[row] = col
            by_col[col] = row
            used_letters.add(letter)

            search(row + 1)

            used_letters.discard(letter)
            del by_col[col]
            placement[row] = None

    search(0)

    return found


def solve_from_board(board, time_limit: float = 30.0) -> Solution:
    """Посчитать расстановку для прочитанного поля, сверив найденных кошек."""
    return solve(board.colors, board.cats, time_limit)