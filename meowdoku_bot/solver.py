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
from typing import Sequence

from .domain import Cell
from .logging_setup import get_logger

log = get_logger("solver")

# Столько решений достаточно, чтобы понять: решение единственное или нет.
AMBIGUOUS_AT = 2


class UniqueSolutionRequired(RuntimeError):
    """Решений нет или их больше одной.

    Поля без единственного решения в игре не бывает, так что исключение —
    это сигнал ошибки чтения, а не штатная ситуация.
    """


@dataclass(frozen=True)
class Solution:
    """Единственная расстановка кошек."""

    size: int
    cats: tuple[Cell, ...]

    def __contains__(self, cell: Cell) -> bool:
        return cell in self.cats

    def __iter__(self):
        return iter(self.cats)

    def __len__(self) -> int:
        return len(self.cats)

    def __str__(self) -> str:
        return "котики: " + ", ".join(str(cat) for cat in self.cats)


def solve_from_board(board, time_limit: float = 30.0) -> Solution:
    return Solver(time_limit=time_limit).solve_board(board)


def _as_cell(value: Cell | tuple[int, int]) -> Cell:
    """Принять и Cell, и пару (строка, столбец)."""
    if isinstance(value, Cell):
        return value
    return Cell(value[0], value[1])


class Solver:
    """Ищет единственную расстановку кошек на поле.

    Обход в глубину по строкам: в строке кошка одна, поэтому на каждом шаге
    выбираем столбец. Ветки отсекаем, когда столбец занят, рядом уже стоит
    кошка или цвет использован.
    """

    def __init__(self, time_limit: float = 30.0, max_solutions: int = AMBIGUOUS_AT) -> None:
        self.time_limit = time_limit
        self.max_solutions = max_solutions

    def solve(
        self,
        colors: Sequence[Sequence[str]],
        found_cats: Sequence[Cell] = (),
    ) -> Solution:
        """Найти единственную расстановку.

        Бросает UniqueSolutionRequired, если решений нет или их больше одной.
        """
        size = len(colors)
        if size == 0:
            raise UniqueSolutionRequired("поле пустое")
        if any(len(row) != size for row in colors):
            raise UniqueSolutionRequired("поле не квадратное")

        known = self._validate_found(colors, size, [_as_cell(cat) for cat in found_cats])
        solutions = self._enumerate(colors, size, known)

        if not solutions:
            detail = f" с учётом найденных кошек {sorted(str(c) for c in known)}" if known else ""
            raise UniqueSolutionRequired(f"решений нет{detail}")

        if len(solutions) >= self.max_solutions:
            raise UniqueSolutionRequired(
                f"решений минимум {len(solutions)} — поле прочитано неверно, тапать нельзя"
            )

        return Solution(size=size, cats=solutions[0])

    def is_unique(
        self,
        colors: Sequence[Sequence[str]],
        found_cats: Sequence[Cell] = (),
    ) -> bool:
        """Единственное ли решение."""
        try:
            self.solve(colors, found_cats)
        except UniqueSolutionRequired:
            return False
        return True

    def solve_board(self, board) -> Solution:
        """Посчитать расстановку для прочитанного поля."""
        return self.solve(board.colors, list(board.cats))

    # --- внутреннее -------------------------------------------------------

    def _validate_found(
        self,
        colors: Sequence[Sequence[str]],
        size: int,
        found_cats: Sequence[Cell],
    ) -> dict[Cell, str]:
        """Проверить найденных кошек на вменяемость.

        Кошка занимает строку, столбец и цвет. Две кошки в одной строке или
        одного цвета означают, что поле прочитано неверно.
        """
        known: dict[Cell, str] = {}
        used_rows: set[int] = set()
        used_cols: set[int] = set()
        used_colors: set[str] = set()

        for cell in sorted(set(found_cats)):
            if not (0 <= cell.row < size and 0 <= cell.col < size):
                raise UniqueSolutionRequired(f"котик {cell} вне поля {size}x{size}")

            if cell.row in used_rows:
                raise UniqueSolutionRequired(
                    f"котики {cell} и ещё один делят строку {cell.row}"
                )
            if cell.col in used_cols:
                raise UniqueSolutionRequired(
                    f"котики {cell} и ещё один делят столбец {cell.col}"
                )

            letter = colors[cell.row][cell.col]
            if letter in used_colors:
                raise UniqueSolutionRequired(
                    f"котик {cell} занимает цвет {letter}, уже занятый"
                )

            used_rows.add(cell.row)
            used_cols.add(cell.col)
            used_colors.add(letter)
            known[cell] = letter

        return known

    def _enumerate(
        self,
        colors: Sequence[Sequence[str]],
        size: int,
        known: dict[Cell, str],
    ) -> list[tuple[Cell, ...]]:
        """Перебрать расстановки обходом в глубину по строкам.

        Возвращает не больше max_solutions расстановок: двух достаточно,
        чтобы признать поле неоднозначным.
        """
        deadline = time.monotonic() + self.time_limit
        solutions: list[tuple[Cell, ...]] = []

        # Столбец каждой строки, None — строка ещё не заполнена.
        placement: list[int | None] = [None] * size
        # Столбец -> строка, чтобы проверка занятости была O(1).
        row_by_column: dict[int, int] = {}
        used_colors: set[str] = set()

        # Найденных кошек ставим сразу: их позиции не выбираются.
        locked_rows: set[int] = set()
        for cell, letter in known.items():
            placement[cell.row] = cell.col
            row_by_column[cell.col] = cell.row
            used_colors.add(letter)
            locked_rows.add(cell.row)

        def search(row: int) -> None:
            if len(solutions) >= self.max_solutions or time.monotonic() > deadline:
                return

            if row == size:
                solutions.append(
                    tuple(Cell(row, col) for row, col in enumerate(placement) if col is not None)
                )
                return

            # Кошка выше по соседней строке, если она там есть.
            previous_cat_column = placement[row - 1] if row > 0 else None

            if row in locked_rows:
                # Найденного котика мы не выбирали, но касаться кошки в строке
                # выше он тоже не должен: иначе в список попадут заведомо
                # неправильные расстановки.
                if previous_cat_column is not None and abs(placement[row] - previous_cat_column) <= 1:
                    return
                search(row + 1)
                return

            for col in range(size):
                if col in row_by_column:
                    continue
                if previous_cat_column is not None and abs(col - previous_cat_column) <= 1:
                    continue

                letter = colors[row][col]
                if letter in used_colors:
                    continue

                placement[row] = col
                row_by_column[col] = row
                used_colors.add(letter)

                search(row + 1)

                used_colors.discard(letter)
                del row_by_column[col]
                placement[row] = None

        search(0)

        if len(solutions) >= self.max_solutions:
            log.debug("поле %dx%d неоднозначно, найдено решений: %d", size, size, len(solutions))
        else:
            log.debug("поле %dx%d: решений %d, время %.3fс", size, size, len(solutions),
                      self.time_limit - max(0.0, deadline - time.monotonic()))

        return solutions
