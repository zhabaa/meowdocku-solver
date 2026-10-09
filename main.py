"""Прохождение уровней Meowdoku.

Цикл: снять экран, понять что на нём, действовать.

  поле        -> решить единственным способом и поставить кошек,
  пройден     -> тапнуть оранжевую кнопку,
  лидеры      -> тапнуть жёлтую надпись,
  неизвестно  -> остановиться.

Расстановка всегда единственная и проверяется до первого тапа, поэтому
попасть в пустую клетку невозможно и жизни не тратятся.

Запуск:
    .venv/bin/python main.py                # крутить уровни
    .venv/bin/python main.py --dry-run      # только показывать решения
    .venv/bin/python main.py --image ПУТЬ   # разобрать сохранённый скрин
    .venv/bin/python main.py --levels 5     # остановиться после пяти уровней
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import emulate
from annotate import annotate
from field import Board
from screens import ScreenKind, detect
from domain import Cell
from solver import InconsistentBoard, solve_from_board

OUT_DIR = Path("img/tmp")
LIVE_SHOT = OUT_DIR / "live.png"

# Как часто опрашивать экран, пока ждём реакцию игры.
POLL_INTERVAL = 1.0
# Сколько секунд ждать реакции, прежде чем повторить тап.
REACTION_TIMEOUT = 6.0
# Сколько повторов тапа подряд, прежде чем сдаться.
MAX_TAP_ATTEMPTS = 3
# Сколько раз переснять экран, если он не опознался: во время анимации
# перехода между экранами кадр читается плохо и через пару секунд нормально.
MAX_SCREEN_RETRIES = 4

NO_LIMIT = 0  # 0 — без ограничения

# Настоящие поля не меньше 4x4. Меньшие — это ореолы вокруг иконок на
# переходных кадрах, а не доски.
MIN_BOARD_SIZE = 4
MAX_BOARD_SIZE = 20


def main() -> int:
    args = parse_args()

    if args.image:
        return run_on_image(Path(args.image))

    if not emulate.is_connected():
        print("Телефон не подключён. Подключи по USB и включи отладку.")
        print("Или запусти с --image путь, чтобы разобрать готовый скриншот.")
        return 1

    return run_loop(dry_run=args.dry_run, max_levels=args.levels, max_steps=args.steps)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Бот для Meowdoku")
    parser.add_argument("--dry-run", action="store_true", help="не тапать, только показывать")
    parser.add_argument("--image", metavar="ПУТЬ", help="разобрать сохранённый скриншот")
    parser.add_argument("--levels", type=int, default=NO_LIMIT, help="сколько уровней пройти")
    parser.add_argument("--steps", type=int, default=NO_LIMIT, help="предел шагов цикла")
    return parser.parse_args()


def run_loop(dry_run: bool, max_levels: int, max_steps: int) -> int:
    """Крутим уровни, пока не попросят остановиться."""
    levels_done = 0
    steps = 0

    while True:
        steps += 1
        if max_steps and steps > max_steps:
            print(f"\nДостигнут предел шагов ({max_steps}). Останавливаюсь.")
            return 0

        screen = shoot_stable()
        if screen is None:
            print(f"Последний скриншот: {LIVE_SHOT}")
            return 1

        if screen.kind == ScreenKind.BOARD:
            if not solve_level(screen.board, LIVE_SHOT, dry_run):
                return 1

            if dry_run:
                print("\n--dry-run: телефон не трогаем.")
                return 0

            # Поле остаётся на экране ещё на пару секунд, пока игра
            # доигрывает анимацию. Без ожидания бот перечитывает то же
            # поле и считает его новым уровнем.
            if not wait_for_change(ScreenKind.BOARD):
                print("Поле не сменилось после постановки кошек.")
                return 0

            levels_done += 1
            print(f"Уровень пройден. Всего: {levels_done}")

            if max_levels and levels_done >= max_levels:
                print(f"\nДостигнут предел уровней ({max_levels}). Останавливаюсь.")
                return 0

        elif screen.kind == ScreenKind.LEVEL_DONE:
            if not tap_until_changed(
                screen.tap_point, "кнопку «уровень пройден»", screen.kind, dry_run
            ):
                return 0

        elif screen.kind == ScreenKind.LEADERBOARD:
            if not tap_until_changed(
                screen.tap_point,
                "надпись «нажмите, чтобы продолжить»",
                screen.kind,
                dry_run,
            ):
                return 0


def inspect_board(board: Board) -> Optional[str]:
    """Проверить доску перед тапами. Вернёт причину, если что-то не так.

    Проверки, которые видно глазом на настоящей доске:
      - котиков не больше, чем размер поля,
      - в каждой строке и столбце найденные котики не делят место,
      - все котики разных цветов,
      - расстановка единственная: если решений много, поле прочиталось неверно.
    """
    n = board.n
    cats = board.cats

    # На живой игре поля от 4x4 и до 20x20. Кадры переходов иногда читаются
    # как поле 1x1 — это ореол вокруг иконки, а не доска.
    if not MIN_BOARD_SIZE <= n <= MAX_BOARD_SIZE:
        return f"поле {n}x{n} — настоящие поля {MIN_BOARD_SIZE}x{MIN_BOARD_SIZE} и крупнее"

    if len(cats) > n:
        return f"найдено {len(cats)} котиков при поле {n}x{n}, а котиков всего {n}"

    rows = [r for r, _ in cats]
    cols = [c for _, c in cats]
    letters = [board.colors[r][c] for r, c in cats]

    if len(set(rows)) != len(rows):
        return "найденные котики делят строку"
    if len(set(cols)) != len(cols):
        return "найденные котики делят столбец"
    if len(set(letters)) != len(letters):
        return "найденные котики одного цвета"

    try:
        solve_from_board(board)
    except InconsistentBoard as error:
        return str(error)

    return None


def shoot_stable():
    """Снять экран и дождаться, пока он перестанет меняться.

    Игра переезжает между экранами с анимацией, и промежуточный кадр читается
    плохо: поле 10x10 собиралось с 12 цветов вместо 10, а кадр перехода после
    тапа по лидерам читался как поле 1x1. Такое проходит за пару секунд,
    поэтому такой кадр просто пропускаем.
    """
    problem = ""

    for attempt in range(1, MAX_SCREEN_RETRIES + 1):
        screen = shoot(LIVE_SHOT)

        if screen.kind == ScreenKind.UNKNOWN:
            problem = f"экран не опознан: {screen.reason}"
        elif screen.kind == ScreenKind.BOARD:
            problem = inspect_board(screen.board)
            if problem is None:
                describe(screen)
                return screen
            problem = f"поле не годится: {problem}"
        else:
            describe(screen)
            return screen

        if attempt == 1:
            print(problem)
        print(f"  пробую ещё раз ({attempt}/{MAX_SCREEN_RETRIES})")
        time.sleep(POLL_INTERVAL)

    print(f"Экран так и не пришёл в норму: {problem}")
    return None


def solve_level(board: Board, shot: Path, dry_run: bool) -> bool:
    """Разобрать поле и поставить кошек. False — продолжать нельзя."""
    print(f"\nПоле {board.n}x{board.n}, найдено котиков: {len(board.cats)}")

    try:
        solution = solve_from_board(board)
    except InconsistentBoard as error:
        print(f"Решение не найдено: {error}")
        annotate(shot, board, OUT_DIR / "failed.png")
        print(f"Скриншот сохранён: {OUT_DIR / 'failed.png'}")
        return False

    found = [Cell(row, col) for row, col in board.cats]
    todo = [cat for cat in solution if cat not in found]
    print(f"Расстановка: {solution}")
    print(f"Осталось поставить: {len(todo)}")

    annotate(shot, board, OUT_DIR / "plan.png", planned=todo)

    if dry_run:
        for cat in todo:
            x, y = board.tap_point(cat.row, cat.col)
            print(f"  {cat} тап в ({x:.0f}, {y:.0f})")
        return True

    for cat in todo:
        x, y = board.tap_point(cat.row, cat.col)
        print(f"  двойной тап {cat} -> ({x:.0f}, {y:.0f})")

        if not place_cat(cat, x, y):
            print(f"Котик {cat} так и не появился.")
            print(f"Последний скриншот: {LIVE_SHOT}")
            return False

    return True


def place_cat(cat: Cell, x: float, y: float) -> bool:
    """Поставить одного котика двойными тапами, пока он не появится.

    Повтор в ту же клетку безопасен: жизнь тратится только за попадание
    в пустую клетку, а мы бьём точно в ту же.
    """
    for attempt in range(1, MAX_TAP_ATTEMPTS + 1):
        emulate.double_tap(x, y)

        if wait_for_cat(cat):
            return True

        print(
            f"  котик в {cat} не появился, "
            f"повторяем тап ({attempt}/{MAX_TAP_ATTEMPTS})"
        )

    return False


def wait_for_cat(cat: Cell) -> bool:
    """Ждать, пока кот появится в нужной клетке.

    Поле, исчезнувшее с экрана, тоже считаем успехом: значит уровень
    закончился раньше, чем мы это заметили.
    """
    for _ in range(int(REACTION_TIMEOUT / POLL_INTERVAL)):
        screen = shoot(LIVE_SHOT)

        if screen.kind != ScreenKind.BOARD:
            return True

        if cat in [Cell(r, c) for r, c in screen.board.cats]:
            return True

        time.sleep(POLL_INTERVAL)

    return False


def tap_until_changed(point: tuple[int, int], what: str, previous: str, dry_run: bool) -> bool:
    """Тапнуть и ждать смены экрана, повторяя тап, пока не сменится.

    Смена экрана определяется по типу, а не по разнице картинок: два
    разных экрана лидеров отличаются сильнее, чем одно поле до и после
    установки трёх кошек.

    False — экран так и не сменился, цикл надо остановить.
    """
    print(f"Тапаю {what} в {point}")

    if dry_run:
        return True

    for attempt in range(1, MAX_TAP_ATTEMPTS + 1):
        emulate.tap(point[0], point[1])

        if wait_for_change(previous):
            return True

        print(f"  экран не изменился, повторяем тап ({attempt}/{MAX_TAP_ATTEMPTS})")

    print(f"Экран не поменялся после {MAX_TAP_ATTEMPTS} тапов: {what}")
    return False


def wait_for_change(previous: str) -> bool:
    """Ждать, пока на экране появится что-то другое."""
    for _ in range(int(REACTION_TIMEOUT / POLL_INTERVAL)):
        if shoot(LIVE_SHOT).kind != previous:
            return True

        time.sleep(POLL_INTERVAL)

    return False


def shoot(path: Path):
    """Снять скриншот и определить, что на нём."""
    emulate.capture(path)
    return detect(path)


def describe(screen) -> None:
    if screen.kind == ScreenKind.LEVEL_DONE:
        print(f"Экран: уровень пройден, кнопка в {screen.tap_point}")
    elif screen.kind == ScreenKind.LEADERBOARD:
        print(f"Экран: таблица лидеров, надпись в {screen.tap_point}")


def run_on_image(path: Path) -> int:
    """Разобрать сохранённый скриншот без телефона."""
    if not path.exists():
        print(f"Нет файла {path}")
        return 1

    screen = detect(path)

    if screen.kind == ScreenKind.LEADERBOARD:
        print(f"Таблица лидеров. Тапнуть надпись в {screen.tap_point}")
        return 0

    if screen.kind == ScreenKind.LEVEL_DONE:
        print(f"Уровень пройден. Тапнуть кнопку в {screen.tap_point}")
        return 0

    if screen.kind != ScreenKind.BOARD:
        print(f"Экран не опознан: {screen.reason}")
        return 1

    board = screen.board
    print(board)
    print(f"\nПалитра: {board.palette}")

    try:
        solution = solve_from_board(board)
    except InconsistentBoard as error:
        print(f"Решение не найдено: {error}")
        return 1

    found = [Cell(row, col) for row, col in board.cats]
    todo = [cat for cat in solution if cat not in found]
    print(f"\n{solution}")
    print(f"Уже найдено: {sorted(board.cats)}")
    print(f"Осталось поставить: {len(todo)}")

    for cat in todo:
        x, y = board.tap_point(cat.row, cat.col)
        print(f"  {cat} тап в ({x:.0f}, {y:.0f})")

    annotate(path, board, OUT_DIR / "preview.png", planned=[(c.row, c.col) for c in todo])
    print(f"\nРазбор сохранён: {OUT_DIR / 'preview.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())