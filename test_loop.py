"""Тесты игрового цикла на подделке телефона.

Подделка отдаёт настоящие скрины и кладёт котика в клетку, куда пришёл
двойной тап. Проверяем главное: бот проходит уровень за одну попытку,
ставит всех кошек ровно по решению и тапает переходы в те точки, что
нашёл детектор экранов.

Запуск: .venv/bin/python test_loop.py
"""

from pathlib import Path
from unittest import mock

import cv2
import numpy as np

from meowdoku_bot.annotate import Annotator
from meowdoku_bot.config import Settings
from meowdoku_bot.domain import Cell, ScreenKind
from fake_phone import SHOTS, FakePhone
from meowdoku_bot.field import Board, BoardReader
from meowdoku_bot.game import EXIT_FAILED, EXIT_OK, BoardValidator, GameBot, LevelPlayer
from meowdoku_bot.screens import BoardScreen, ScreenClassifier
from meowdoku_bot.solver import Solver, UniqueSolutionRequired

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def build_bot(phone: FakePhone, settings: Settings | None = None, shoot=None):
    """Собрать бота, у которого вместо телефона подделка."""
    resolved = settings or Settings()
    work_dir = phone.out
    reader = BoardReader(resolved)
    solver = Solver(time_limit=resolved.timing.solve_time_limit)
    classifier = ScreenClassifier(resolved, reader)
    annotator = Annotator()

    player = LevelPlayer(
        device=phone,
        classifier=classifier,
        solver=solver,
        annotator=annotator,
        settings=resolved,
        work_dir=work_dir,
    )

    bot = GameBot(
        device=phone,
        classifier=classifier,
        player=player,
        validator=BoardValidator(resolved, solver),
        annotator=annotator,
        settings=resolved,
        work_dir=work_dir,
    )

    if shoot is not None:
        original = bot._shoot
        bot._shoot = lambda: shoot(original)

    return bot


def run(phone: FakePhone, max_levels: int = 1, max_steps: int = 40, dry_run: bool = False) -> int:
    with mock.patch("time.sleep"):
        return build_bot(phone).run(max_levels=max_levels, max_steps=max_steps, dry_run=dry_run)


def tiny_board(size: int = 1) -> Board:
    """Поле, которое читается как доска, но доской не является."""
    return Board(
        size=size,
        colors=(("A",),) * size,
        cats=frozenset((0, 0)) if size == 1 else frozenset(),
        centers=tuple((0.0, 0.0) for _ in range(size * size)),
        tap_points=tuple((0.0, 0.0) for _ in range(size * size)),
        palette=tuple((0, 0, 0) for _ in range(size)),
        cell_w=10,
        cell_h=10,
    )


def test_single_level_one_pass() -> None:
    """Пустое поле 8x8: 8 двойных тапов, ни одного повтора."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    code = run(phone)

    check(code == EXIT_OK, f"вернулся код {code}, ожидался 0")
    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")
    check(not phone.taps, f"одиночных тапов {len(phone.taps)}, ожидался 0")


def test_found_cats_not_tapped() -> None:
    """shot_8: один кот уже найден, значит 7 двойных тапов."""
    phone = FakePhone(screens=[SHOTS / "shot_8.jpg"])
    run(phone)

    check(len(phone.double_taps) == 7, f"двойных тапов {len(phone.double_taps)}, ожидалось 7")


def test_taps_match_solution() -> None:
    """Каждый тап должен попасть в клетку из решения."""
    board = BoardReader().read_path(str(SHOTS / "shot_8.jpg"))
    solution = Solver().solve(board.colors, [Cell(r, c) for r, c in board.cats])
    expected = {
        tuple(map(int, board.tap_point(cat.row, cat.col)))
        for cat in solution
        if (cat.row, cat.col) not in board.cats
    }

    phone = FakePhone(screens=[SHOTS / "shot_8.jpg"])
    run(phone)

    check(set(phone.double_taps) == expected, f"тапы не совпали с решением: {sorted(phone.double_taps)}")


def test_every_cat_lands() -> None:
    """После прохода на поле должно быть ровно N котиков."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    run(phone)

    board = BoardReader().read_path(str(phone.out / "probe.png"))
    check(len(board.cats) == 8, f"котиков на поле {len(board.cats)}, ожидалось 8")


def test_leaderboard_then_board() -> None:
    """Лидеры: одиночный тап в надпись, дальше бот берётся за поле."""
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg", SHOTS / "shot_5.jpg"])
    run(phone)

    check(len(phone.taps) >= 1, "одиночных тапов не было")
    check(phone.taps[0] == (536, 2111), f"тапнул в {phone.taps[0]}, ожидалось (536, 2111)")
    check(len(phone.double_taps) == 8, f"после лидеров двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_level_done_button() -> None:
    """Экран пройденного: одиночный тап в оранжевую кнопку."""
    phone = FakePhone(screens=[SHOTS / "shot_2.jpg", SHOTS / "shot_5.jpg"])
    run(phone)

    check(len(phone.taps) >= 1, "одиночных тапов не было")
    check(phone.taps[0] == (540, 1840), f"тапнул в {phone.taps[0]}, ожидалось (540, 1840)")


def test_repeated_tap_when_screen_unchanged() -> None:
    """Если экран не меняется, тап повторяется в ту же точку."""
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg"])
    run(phone, max_steps=3)

    check(len(phone.taps) >= 2, f"тапов {len(phone.taps)}, ожидались повторы")
    check(len(set(phone.taps)) == 1, f"тапы разъехались: {set(phone.taps)}")


def test_gives_up_when_screen_never_changes() -> None:
    """Если экран так и не сменился, бот сдаётся, а не висит и не молчит.

    Переход пробуется max_stuck_transitions раз подряд — кнопка могла уехать,
    и её надо найти заново. Когда и это не помогло, телефон заблокирован.
    """
    timing = Settings().timing
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg"])
    code = run(phone, max_steps=50)

    check(code == EXIT_FAILED, f"вернулся код {code}, ожидался 1")
    check(
        len(phone.taps) == timing.max_stuck_transitions * timing.max_tap_attempts,
        f"тапов {len(phone.taps)}, ожидалось "
        f"{timing.max_stuck_transitions * timing.max_tap_attempts}",
    )


def test_recovers_from_stuck_transition() -> None:
    """Промахнувшийся тап по кнопке не убивает прогон.

    Кнопка «уровень пройден» прыгает по вертикали между кадрами, и тап в
    сохранённую точку иногда не срабатывает. Раньше бот на этом тихо
    завершался даже с --levels 0; теперь он переснимает экран, ищет кнопку
    заново и доигрывает уровень.
    """
    phone = FakePhone(screens=[SHOTS / "shot_2.jpg", SHOTS / "shot_5.jpg"])
    bot = build_bot(phone)
    real_tap = bot._tap_until_changed
    calls = {"n": 0}

    def flaky_tap(screen, dry_run=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return False
        return real_tap(screen, dry_run)

    bot._tap_until_changed = flaky_tap

    with mock.patch("time.sleep"):
        code = bot.run(max_levels=1, max_steps=30)

    check(code == EXIT_OK, f"вернулся код {code}, ожидался 0")
    check(calls["n"] >= 2, f"переход опробован {calls['n']} раз, бот не попробовал снова")
    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_repeats_double_tap_when_cat_missing() -> None:
    """Если кот не появился, двойной тап повторяется в ту же клетку."""
    broken = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    broken.double_tap = lambda x, y: broken.double_taps.append((int(x), int(y)))

    run(broken, max_levels=1, max_steps=3)

    first = broken.double_taps[0]
    repeats = broken.double_taps[:3]
    check(len(repeats) == 3, f"повторов {len(repeats)}, ожидалось 3")
    check(set(repeats) == {first}, f"повтор ушёл в другую клетку: {set(repeats)}")


def test_tiny_board_rejected() -> None:
    """Поле 1x1 — не доска, а ореол вокруг иконки на переходном кадре."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    problem = BoardValidator(Settings(), Solver()).problem_with(tiny_board())

    check(problem is not None, "поле 1x1 прошло проверку")
    check(problem is not None and "1x1" in problem, f"в сообщении нет размера: {problem}")


def test_too_many_cats_rejected() -> None:
    """Экран «уровень пройден» подсветкой поверх поля даёт лишних котиков."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    board = Board(
        size=10,
        colors=tuple(tuple("ABCDEFGHIJ" for _ in range(10)) for _ in range(10)),
        cats=frozenset((row, col) for row in range(10) for col in range(10)),
        centers=tuple((0.0, 0.0) for _ in range(100)),
        tap_points=tuple((0.0, 0.0) for _ in range(100)),
        palette=tuple((0, 0, 0) for _ in range(10)),
        cell_w=10,
        cell_h=10,
    )

    problem = BoardValidator(Settings(), Solver()).problem_with(board)
    check(problem is not None, "100 котиков на поле 10x10 прошли проверку")


def test_real_boards_pass_validation() -> None:
    """Настоящие доски проверку проходят."""
    validator = BoardValidator(Settings(), Solver())
    reader = BoardReader()

    for name in ("live_10x10_empty.png", "live_9x9_cat_on_grey.png",
                 "live_10x10_one_cat.png", "shot_5.jpg"):
        board = reader.read_path(str(SHOTS / name))
        problem = validator.problem_with(board)
        check(problem is None, f"{name}: проверка отклонила доску: {problem}")


def test_overlay_board_does_not_pass() -> None:
    """Экран «уровень пройден» поверх поля должен отклоняться."""
    try:
        board = BoardReader().read_path(str(SHOTS / "bad21_cats.png"))
    except Exception:
        # Отказ на этапе чтения — тоже правильное поведение.
        return

    problem = BoardValidator(Settings(), Solver()).problem_with(board)
    check(problem is not None, "поле с подсветкой прошло проверку")


def test_retries_transition_frame() -> None:
    """Кадр во время анимации читается плохо — бот переснимает экран."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    calls = {"n": 0}
    original = phone.capture

    def flaky_capture(destination):
        calls["n"] += 1
        if calls["n"] <= 2:
            local = Path(destination)
            local.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(local), np.full((2340, 1080, 3), 250, dtype=np.uint8))
            return local
        return original(destination)

    phone.capture = flaky_capture
    code = run(phone, max_steps=10)

    check(code == EXIT_OK, f"вернулся код {code}, ожидался 0")
    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_retries_bad_board_frame() -> None:
    """Поле 1x1 на переходе переснимается, а не роняет бота."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    bot = build_bot(phone)
    real_shoot = bot._shoot
    calls = {"n": 0}

    def counting_shoot():
        calls["n"] += 1
        if calls["n"] <= 2:
            return BoardScreen(board=tiny_board())
        return real_shoot()

    bot._shoot = counting_shoot

    with mock.patch("time.sleep"):
        code = bot.run(max_levels=1, max_steps=10)

    check(code == EXIT_OK, f"вернулся код {code}, ожидался 0")
    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_stops_on_ambiguous_board() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    bot = build_bot(phone)

    with mock.patch.object(Solver, "solve", side_effect=UniqueSolutionRequired("решений минимум 2")), \
         mock.patch("time.sleep"):
        code = bot.run(max_levels=1, max_steps=10)

    check(code == EXIT_FAILED, f"вернулся код {code}, ожидался 1")
    check(not phone.double_taps, "тапали на неоднозначном поле")


def test_stops_on_unknown_screen() -> None:
    blank = SHOTS / "BLANK_LOOP.png"
    cv2.imwrite(str(blank), np.full((2340, 1080, 3), 250, dtype=np.uint8))
    phone = FakePhone(screens=[blank])

    try:
        code = run(phone, max_steps=5)
        check(code == EXIT_FAILED, f"вернулся код {code}, ожидался 1")
        check(not phone.taps, "тапали на пустом экране")
    finally:
        blank.unlink(missing_ok=True)


def test_dry_run_never_taps() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    run(phone, dry_run=True)

    check(not phone.taps, f"в dry-run одиночных тапов {len(phone.taps)}")
    check(not phone.double_taps, f"в dry-run двойных тапов {len(phone.double_taps)}")


def test_level_counted_once() -> None:
    """Уровень не засчитывается дважды на одном поле.

    Игра держит поле на экране ещё пару секунд после последнего котика.
    Без ожидания бот перечитывает то же поле и считает его новым уровнем.
    """
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    run(phone, max_levels=1, max_steps=10)

    check(
        len(phone.double_taps) == 8,
        f"двойных тапов {len(phone.double_taps)}, ожидалось 8: похоже, уровень посчитан дважды",
    )


def test_levels_limit_stops_loop() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    run(phone, max_levels=1)

    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_step_limit_stops_loop() -> None:
    timing = Settings().timing
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg"])
    run(phone, max_levels=0, max_steps=3)

    check(
        len(phone.taps) <= timing.max_tap_attempts * 3,
        f"тапов {len(phone.taps)} при пределе шагов 3",
    )


def main() -> int:
    for test in (
        test_single_level_one_pass,
        test_found_cats_not_tapped,
        test_taps_match_solution,
        test_every_cat_lands,
        test_leaderboard_then_board,
        test_level_done_button,
        test_repeated_tap_when_screen_unchanged,
        test_gives_up_when_screen_never_changes,
        test_recovers_from_stuck_transition,
        test_repeats_double_tap_when_cat_missing,
        test_tiny_board_rejected,
        test_too_many_cats_rejected,
        test_real_boards_pass_validation,
        test_overlay_board_does_not_pass,
        test_retries_transition_frame,
        test_retries_bad_board_frame,
        test_stops_on_ambiguous_board,
        test_stops_on_unknown_screen,
        test_dry_run_never_taps,
        test_level_counted_once,
        test_levels_limit_stops_loop,
        test_step_limit_stops_loop,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты игрового цикла прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
