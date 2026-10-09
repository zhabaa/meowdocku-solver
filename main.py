"""Прохождение одного поля Meowdoku.

Логика простая и безошибочная: читаем поле, находим единственную
расстановку кошек, ставим их двойным тапом. Крестики не ставим — они
только тратят время.

Если поле прочиталось неоднозначно или не имеет решения, бот останавливается
и сохраняет скриншот. В игре три жизни, гадать нельзя.

Запуск:
    .venv/bin/python main.py                 # с телефоном
    .venv/bin/python main.py --dry-run       # только показать решение
    .venv/bin/python main.py --image путь    # разобрать сохранённый скрин
"""

import argparse
import sys
import time
from pathlib import Path

import emulate
from annotate import annotate
from field import Board, BoardReadError, read_board
from solver import InconsistentBoard, Solution, solve_from_board

OUT_DIR = Path("img/tmp")
# Сколько ждать реакции игры после двойного тапа, перед новым скриншотом.
SETTLE_AFTER_TAP = 0.6
# Сколько ждать после последнего котика, чтобы поймать смену экрана.
SETTLE_AFTER_LAST = 1.5


def main() -> int:
    args = parse_args()

    if args.image:
        return run_on_image(Path(args.image), dry_run=True)

    if not emulate.is_connected():
        print("Телефон не подключён. Подключи и включи отладку по USB.")
        print("Или запусти с --image путь, чтобы разобрать готовый скриншот.")
        return 1

    return play(dry_run=args.dry_run)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Бот для Meowdoku")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="не тапать, только показать поле и расстановку",
    )
    parser.add_argument(
        "--image",
        metavar="ПУТЬ",
        help="разобрать сохранённый скриншот вместо съёмки с телефона",
    )
    return parser.parse_args()


def play(dry_run: bool) -> int:
    shot = OUT_DIR / "live.png"

    board = shoot(shot)
    if board is None:
        print("Поле на экране не найдено. Открой уровень в игре.")
        return 1

    solution = plan(board, shot)
    if solution is None:
        return 1

    to_place = [cell for cell in solution if cell not in board.cats]
    print(f"Котов найдено: {len(board.cats)}, осталось поставить: {len(to_place)}")

    annotate(shot, board, OUT_DIR / "step_00_plan.png", planned=to_place)

    if dry_run:
        print("\n--dry-run: телефон не трогаем.")
        for row, col in to_place:
            x, y = board.tap_point(row, col)
            print(f"  ({row},{col}) тап в ({x:.0f}, {y:.0f})")
        return 0

    placed: list[tuple[int, int]] = []

    for index, (row, col) in enumerate(to_place, start=1):
        x, y = board.tap_point(row, col)
        print(f"[{index}/{len(to_place)}] двойной тап в ({row},{col}) -> ({x:.0f}, {y:.0f})")
        emulate.double_tap(x, y)
        placed.append((row, col))
        time.sleep(SETTLE_AFTER_TAP)

        check = shoot(OUT_DIR / f"step_{index:02d}.png")
        if check is None:
            print("Поле исчезло с экрана. Возможно, уровень пройден.")
            break

        annotate(
            OUT_DIR / f"step_{index:02d}.png",
            check,
            OUT_DIR / f"step_{index:02d}_view.png",
            planned=[c for c in to_place if c not in check.cats],
        )

        still_there = [c for c in placed if c not in check.cats]
        if still_there:
            print(f"  не появились котики: {still_there}")

    verify(shot)
    return 0


def verify(shot: Path) -> None:
    """Финальная сверка: все ли котики на месте."""
    time.sleep(SETTLE_AFTER_LAST)
    board = shoot(shot)

    if board is None:
        print("Поле исчезло с экрана: уровень, похоже, пройден.")
        return

    print(f"На поле {len(board.cats)} котиков из {board.n}.")

    if len(board.cats) != board.n:
        print("Не все котики на месте.")
        annotate(shot, board, OUT_DIR / "final.png")
        return

    try:
        solution = solve_from_board(board)
    except InconsistentBoard as error:
        print(f"Поле не сходится: {error}")
        return

    print(f"Поле доиграно верно: {solution}")


def shoot(path: Path) -> Board | None:
    """Снять скриншот и прочитать поле. None — поля на экране нет."""
    emulate.capture(path)

    try:
        return read_board(str(path))
    except BoardReadError as error:
        print(f"Поле не прочитано: {error}")
        return None


def plan(board: Board, shot: Path | None = None) -> Solution | None:
    """Найти единственную расстановку. None — тапать нельзя."""
    try:
        solution = solve_from_board(board)
    except InconsistentBoard as error:
        print(f"Решение не найдено: {error}")
        if shot is not None:
            annotate(shot, board, OUT_DIR / "failed.png")
            print(f"Скриншот сохранён: {OUT_DIR / 'failed.png'}")
        return None

    print(f"Расстановка найдена: {solution}")
    return solution


def run_on_image(path: Path, dry_run: bool = True) -> int:
    """Разобрать сохранённый скриншот без телефона."""
    if not path.exists():
        print(f"Нет файла {path}")
        return 1

    try:
        board = read_board(str(path))
    except BoardReadError as error:
        print(f"Поле не прочитано: {error}")
        return 1

    print(board)
    print(f"\nПалитра: {board.palette}")

    solution = plan(board, path)
    if solution is None:
        return 1

    to_place = [cell for cell in solution if cell not in board.cats]
    print(f"\n{solution}")
    print(f"Уже найдено: {sorted(board.cats)}")
    print(f"Осталось поставить: {len(to_place)}")

    for row, col in to_place:
        x, y = board.tap_point(row, col)
        print(f"  ({row},{col}) тап в ({x:.0f}, {y:.0f})")

    annotate(path, board, OUT_DIR / "preview.png", planned=to_place)
    print(f"\nРазбор сохранён: {OUT_DIR / 'preview.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())