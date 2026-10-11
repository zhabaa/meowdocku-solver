import argparse
import sys
from pathlib import Path

from meowdoku_bot.annotate import Annotator, annotate
from meowdoku_bot.config import DEFAULT_LOG_FILE, Settings, from_env
from meowdoku_bot.domain import Cell
from meowdoku_bot.field import BoardReader
from meowdoku_bot.game import EXIT_FAILED, EXIT_OK, BoardValidator, GameBot, LevelPlayer
from meowdoku_bot.logging_setup import setup_logging
from meowdoku_bot.screens import ScreenClassifier, ScreenKind
from meowdoku_bot.solver import Solver, UniqueSolutionRequired

DEFAULT_MAX_LEVELS = 1
DEFAULT_MAX_STEPS = 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Бот для Meowdoku")
    parser.add_argument("--levels", type=int, default=DEFAULT_MAX_LEVELS, help="сколько уровней пройти, 0 — без ограничения")
    parser.add_argument("--steps", type=int, default=DEFAULT_MAX_STEPS, help="предел шагов цикла, 0 — без ограничения")
    parser.add_argument("--dry-run", action="store_true", help="не тапать, только показывать")
    parser.add_argument("--image", metavar="ПУТЬ", help="разобрать сохранённый скриншот")
    parser.add_argument("--verbose", action="store_true", help="подробный лог в консоль")
    parser.add_argument("--log", metavar="ПУТЬ", default=str(DEFAULT_LOG_FILE), help="куда писать лог")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logger = setup_logging(verbose=args.verbose, log_file=args.log)
    settings = from_env()
    logger.debug("настройки:\n%s", settings.describe())

    if args.image:
        return run_on_image(Path(args.image), settings)

    bot = build(settings)

    if not bot.device.is_connected():
        logger.error(
            "Телефон не подключён. Подключи по USB MIDI. "
            "Или запусти с --image путь."
        )
        return EXIT_FAILED

    return bot.run(max_levels=args.levels, max_steps=args.steps, dry_run=args.dry_run)


def build(settings: Settings) -> GameBot:
    """Собрать бота из настоящих или подставленных частей."""
    from meowdoku_bot.device import AdbDevice

    work_dir = Path(settings.device.work_dir)
    reader = BoardReader(settings)
    solver = Solver(time_limit=settings.timing.solve_time_limit)
    classifier = ScreenClassifier(settings, reader)
    annotator = Annotator()
    device = AdbDevice(settings)

    return GameBot(
        device=device,
        classifier=classifier,
        player=LevelPlayer(
            device=device,
            classifier=classifier,
            solver=solver,
            annotator=annotator,
            settings=settings,
            work_dir=work_dir,
        ),
        validator=BoardValidator(settings, solver),
        annotator=annotator,
        settings=settings,
        work_dir=work_dir,
    )


def run_on_image(path: Path, settings: Settings) -> int:

    if not path.exists():
        print(f"нет файла {path}")
        return EXIT_FAILED

    classifier = ScreenClassifier(settings)
    screen = classifier.classify(path)

    if screen.kind == ScreenKind.LEADERBOARD:
        print(f"таблица лидеров. Тапнуть надпись в {screen.tap_point}")
        return EXIT_OK

    if screen.kind == ScreenKind.LEVEL_DONE:
        print(f"уровень пройден. Тапнуть кнопку в {screen.tap_point}")
        return EXIT_OK

    if screen.kind != ScreenKind.BOARD:
        print(f"экран не опознан: {screen.reason}")
        return EXIT_FAILED

    board = screen.board
    print(board)
    print(f"\nПалитра: {board.palette}")

    solver = Solver(time_limit=settings.timing.solve_time_limit)
    try:
        solution = solver.solve(
            colors=board.colors, 
            found_cats=[Cell(row, col) for row, col in board.cats]
        )

    except UniqueSolutionRequired as error:
        print(f"Решение не найдено: {error}")
        return EXIT_FAILED

    already_found = [Cell(row, col) for row, col in board.cats]
    todo = [cat for cat in solution if cat not in already_found]

    print(f"\n{solution}")
    print(f"Уже найдено: {sorted(str(cat) for cat in already_found)}")
    print(f"Осталось поставить: {len(todo)}")

    for cat in todo:
        x, y = board.tap_point(cat.row, cat.col)
        print(f"  {cat} тап в ({x:.0f}, {y:.0f})")

    preview = Path(settings.device.work_dir) / "preview.png"
    annotate(path, board, preview, planned=todo)
    print(f"\nРазбор сохранён: {preview}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
