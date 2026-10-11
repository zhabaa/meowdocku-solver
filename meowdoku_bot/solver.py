import time
from collections.abc import Sequence
from dataclasses import dataclass

from .domain import Cell
from .logging_setup import get_logger

log = get_logger("solver")

AMBIGUOUS_AT = 2


class UniqueSolutionRequired(RuntimeError):
    """Решений нет или их больше одной"""


@dataclass(frozen=True)
class Solution:
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
    if isinstance(value, Cell):
        return value

    return Cell(value[0], value[1])


class Solver:
    def __init__(self, time_limit: float = 30.0, max_solutions: int = AMBIGUOUS_AT) -> None:
        self.time_limit = time_limit
        self.max_solutions = max_solutions

    def solve(self, colors: Sequence[Sequence[str]], 
              found_cats: Sequence[Cell] = ()) -> Solution:

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

    def is_unique(self, colors: Sequence[Sequence[str]], 
                  found_cats: Sequence[Cell] = ()) -> bool:

        try:
            self.solve(colors, found_cats)

        except UniqueSolutionRequired:
            return False

        return True

    def solve_board(self, board) -> Solution:
        return self.solve(board.colors, list(board.cats))


    def _validate_found(self, colors: Sequence[Sequence[str]], size: int, 
                        found_cats: Sequence[Cell]) -> dict[Cell, str]:

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

    def _enumerate(self, colors: Sequence[Sequence[str]], size: int, 
                   known: dict[Cell, str]) -> list[tuple[Cell, ...]]:

        deadline = time.monotonic() + self.time_limit
        solutions: list[tuple[Cell, ...]] = []

        placement: list[int | None] = [None] * size

        row_by_column: dict[int, int] = {}

        used_colors: set[str] = set()
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

            previous_cat_column = placement[row - 1] if row > 0 else None

            if row in locked_rows:
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
