import time
from pathlib import Path
from typing import Optional

from .annotate import Annotator
from .config import Settings
from .domain import Cell, ScreenKind
from .field import Board
from .logging_setup import get_logger
from .screens import Screen, ScreenClassifier, TapScreen
from .solver import Solver, UniqueSolutionRequired

log = get_logger("game")

EXIT_OK = 0
EXIT_FAILED = 1


class BoardValidator:

    def __init__(self, settings: Settings, solver: Solver) -> None:
        self.timing = settings.timing
        self.solver = solver

    def problem_with(self, board: Board) -> str | None:

        size = board.size

        if not self.timing.min_board_size <= size <= self.timing.max_board_size:
            return (
                f"поле {size}x{size} — настоящие поля "
                f"{self.timing.min_board_size}x{self.timing.min_board_size} и крупнее"
            )

        cats = [Cell(row, col) for row, col in board.cats]

        if len(cats) > size:
            return f"найдено {len(cats)} котиков при поле {size}x{size}, а котиков всего {size}"

        if len({cat.row for cat in cats}) != len(cats):
            return "найденные котики делят строку"
        
        if len({cat.col for cat in cats}) != len(cats):
            return "найденные котики делят столбец"

        letters = [board.colors[cat.row][cat.col] for cat in cats]
        
        if len(set(letters)) != len(letters):
            return "найденные котики одного цвета"

        try:
            self.solver.solve(board.colors, cats)
        
        except UniqueSolutionRequired as error:
            return str(error)

        return None


class LevelPlayer:

    def __init__(self, device, classifier: ScreenClassifier, solver: Solver, 
                 annotator: Annotator, settings: Settings, work_dir: Path) -> None:
        self.device = device
        self.classifier = classifier
        self.solver = solver
        self.annotator = annotator
        self.timing = settings.timing
        self.work_dir = work_dir
        self.live_shot = work_dir / "live.png"

    def play(self, board: Board, dry_run: bool) -> bool:
        log.info("поле %dx%d, найдено котиков: %d", board.size, board.size, len(board.cats))

        try:
            solution = self.solver.solve(board.colors, [Cell(r, c) for r, c in board.cats])
        
        except UniqueSolutionRequired as error:
            log.error("решение не найдено: %s", error)
            self._save_failure(board)
            return False

        already_found = [Cell(row, col) for row, col in board.cats]
        todo = [cat for cat in solution if cat not in already_found]

        log.info("расстановка: %s", solution)
        log.info("осталось поставить: %d", len(todo))

        self.annotator.render(self.live_shot, board, self.work_dir / "plan.png", planned=todo)

        if dry_run:
            for cat in todo:
                x, y = board.tap_point(cat.row, cat.col)
                log.info("бы тапнул %s в (%.0f, %.0f)", cat, x, y)
        
            return True

        for cat in todo:
            if not self._place_cat(board, cat):
                log.error("котик %s так и не появился", cat)
        
                return False

        return True

    def _place_cat(self, board: Board, cat: Cell) -> bool:
        x, y = board.tap_point(cat.row, cat.col)

        for attempt in range(1, self.timing.max_tap_attempts + 1):
            log.info("двойной тап %s -> (%.0f, %.0f), попытка %d", cat, x, y, attempt)
            self.device.double_tap(x, y)

            if self._wait_for_cat(cat):
                return True

            log.info("котик в %s не появился, повторяем тап (%d/%d)",
                     cat, attempt, self.timing.max_tap_attempts)

        return False

    def _wait_for_cat(self, cat: Cell) -> bool:
        for _ in range(self._polls()):
            screen = self._shoot()

            if screen.kind != ScreenKind.BOARD:
                return True

            if cat in [Cell(row, col) for row, col in screen.board.cats]:
                return True

            time.sleep(self.timing.poll_interval)

        return False

    def _polls(self) -> int:
        return int(self.timing.reaction_timeout / self.timing.poll_interval)

    def _shoot(self) -> Screen:
        self.device.capture(self.live_shot)
        return self.classifier.classify(self.live_shot)

    def _save_failure(self, board: Board) -> None:
        path = self.work_dir / "failed.png"
        self.annotator.render(self.live_shot, board, path)
        log.error("скриншот сохранён: %s", path)


class GameBot:

    def __init__(self, device, classifier: ScreenClassifier, player: LevelPlayer, 
                 validator: BoardValidator, annotator: Annotator, 
                 settings: Settings,work_dir: Path) -> None:

        self.device = device
        self.classifier = classifier
        self.player = player
        self.validator = validator
        self.annotator = annotator
        self.timing = settings.timing
        self.work_dir = work_dir
        self.live_shot = work_dir / "live.png"

    def run(self, max_levels: int = 1, max_steps: int = 0, dry_run: bool = False) -> int:
        levels_done = 0
        steps = 0
        stuck = 0

        while True:
            steps += 1

            if max_steps and steps > max_steps:
                log.info("достигнут предел шагов (%d). Останавливаюсь.", max_steps)

                return EXIT_OK

            screen = self._shoot_stable()

            if screen is None:
                log.error("последний скриншот: %s", self.live_shot)

                return EXIT_FAILED

            if screen.kind == ScreenKind.BOARD:
                problem = self.validator.problem_with(screen.board)

                if problem is not None:
                    log.error("поле не годится: %s", problem)
                    log.error("последний скриншот: %s", self.live_shot)

                    return EXIT_FAILED

                if not self.player.play(screen.board, dry_run):
                    return EXIT_FAILED

                if dry_run:
                    log.info("--dry-run: телефон не трогаем.")
                    return EXIT_OK

                if not self._wait_for_change(ScreenKind.BOARD):
                    log.info("поле не сменилось после постановки кошек.")

                    return EXIT_OK

                levels_done += 1
                log.info("уровень пройден. Всего: %d", levels_done)
                stuck = 0

                if max_levels and levels_done >= max_levels:
                    log.info("достигнут предел уровней (%d). Останавливаюсь.", max_levels)

                    return EXIT_OK

            else:
                if self._tap_until_changed(screen, dry_run):
                    stuck = 0
                    continue

                stuck += 1

                log.warning("переход не сработал %d раз подряд", stuck)

                if stuck >= self.timing.max_stuck_transitions:

                    log.error(
                        "экран не меняется после %d попыток подряд: телефон "
                        "заблокирован или игра закрыта",
                        stuck,
                    )

                    log.error("последний скриншот: %s", self.live_shot)

                    return EXIT_FAILED

    def _shoot_stable(self) -> Optional[Screen]:
        problem = ""

        for attempt in range(1, self.timing.max_screen_retries + 1):
            screen = self._shoot()

            if screen.kind == ScreenKind.UNKNOWN:
                problem = f"экран не опознан: {screen.reason}"

            elif screen.kind == ScreenKind.BOARD:
                problem = self.validator.problem_with(screen.board)

                if problem is None:
                    log.info("экран: %s", screen.describe())

                    return screen

                problem = f"поле не годится: {problem}"

            else:
                log.info("экран: %s", screen.describe())
                return screen

            if attempt == 1:
                log.info(problem)

            log.info("пробую ещё раз (%d/%d)", attempt, self.timing.max_screen_retries)

            time.sleep(self.timing.poll_interval)

        log.error("экран так и не пришёл в норму: %s", problem)
        return None

    def _tap_until_changed(self, screen: Screen, dry_run: bool) -> bool:
        assert isinstance(screen, TapScreen), "тапать можно только экран с точкой"
        point = screen.tap_point

        log.info("тапаю %s", screen.describe())

        if dry_run:
            return True

        for attempt in range(1, self.timing.max_tap_attempts + 1):
            self.device.tap(point[0], point[1])

            if self._wait_for_change(screen.kind):
                return True

            log.info("экран не изменился, повторяем тап (%d/%d)", attempt, self.timing.max_tap_attempts)

        log.info("экран не поменялся после %d тапов: %s", self.timing.max_tap_attempts, screen.what)

        return False

    def _wait_for_change(self, previous: ScreenKind) -> bool:

        polls = int(self.timing.reaction_timeout / self.timing.poll_interval)

        for _ in range(polls):
            if self._shoot().kind != previous:
                return True

            time.sleep(self.timing.poll_interval)

        return False

    def _shoot(self) -> Screen:
        self.device.capture(self.live_shot)
        return self.classifier.classify(self.live_shot)
