from dataclasses import dataclass
from enum import StrEnum
from typing import NamedTuple


class ScreenKind(StrEnum):
    BOARD = "board"
    LEVEL_DONE = "level_done"
    LEADERBOARD = "leaderboard"
    UNKNOWN = "unknown"


@dataclass(frozen=True, order=True)
class Cell:
    row: int
    col: int

    def __str__(self) -> str:
        return f"({self.row},{self.col})"


class CellBox(NamedTuple):
    left: int
    top: int
    width: int
    height: int

    @property
    def center_x(self) -> float:
        return self.left + self.width / 2

    @property
    def center_y(self) -> float:
        return self.top + self.height / 2

    @property
    def smaller_side(self) -> int:
        return min(self.width, self.height)

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.left + self.width and \
            self.top <= y < self.top + self.height
