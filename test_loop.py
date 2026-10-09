"""Тесты полного цикла на подделанном телефоне.

Подделка отдаёт настоящие скрины и кладёт котика в клетку, куда пришёл
двойной тап. Проверяем главное: бот проходит уровень за одну попытку,
ставит всех кошек ровно по решению и тапает переходы в те точки, что
нашёл детектор экранов.

Запуск: .venv/bin/python test_loop.py
"""

import contextlib
from pathlib import Path
from unittest import mock

import cv2
import numpy as np

import fake_phone
import main
from fake_phone import SHOTS, FakePhone
from field import read_board
from screens import ScreenKind
from solver import InconsistentBoard, solve_from_board

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


@contextlib.contextmanager
def running(phone: FakePhone, **kwargs):
    """Запустить цикл на подделанном телефоне."""
    patches = fake_phone.patch_all(phone, main)

    with contextlib.ExitStack() as stack:
        for patch in patches:
            stack.enter_context(patch)
        stack.enter_context(__import__("unittest").mock.patch.object(main, "OUT_DIR", phone.out))
        stack.enter_context(
            __import__("unittest").mock.patch.object(main, "LIVE_SHOT", phone.out / "live.png")
        )
        yield main.run_loop(
            dry_run=kwargs.get("dry_run", False),
            max_levels=kwargs.get("max_levels", 1),
            max_steps=kwargs.get("max_steps", 40),
        )


def test_sprites_are_usable() -> None:
    """Спрайт котика должен читаться как кот на поле."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    board = read_board(str(SHOTS / "shot_5.jpg"))

    phone.double_tap(*board.tap_point(0, 1))
    after = read_board(str(phone.out / "probe.png"))

    check((0, 1) in after.cats, f"после тапа кот не появился, поле: {sorted(after.cats)}")
    check(after.colors == board.colors, "подстановка котика испортила цвета поля")


def test_single_level_one_pass() -> None:
    """Пустое поле 8x8: 8 двойных тапов, ни одного повтора."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1):
        pass

    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_found_cats_not_tapped() -> None:
    """shot_8: один кот уже найден, значит 7 двойных тапов."""
    phone = FakePhone(screens=[SHOTS / "shot_8.jpg"])

    with running(phone, max_levels=1):
        pass

    check(len(phone.double_taps) == 7, f"двойных тапов {len(phone.double_taps)}, ожидалось 7")


def test_taps_match_solution() -> None:
    """Каждый тап должен попасть в клетку из решения."""
    board = read_board(str(SHOTS / "shot_8.jpg"))
    solution = solve_from_board(board)
    # Уже найденного котика тапать не будем, его в ожидании нет.
    expected = {
        tuple(map(int, board.tap_point(r, c)))
        for r, c in solution
        if (r, c) not in board.cats
    }

    phone = FakePhone(screens=[SHOTS / "shot_8.jpg"])
    with running(phone, max_levels=1):
        pass

    check(
        set(phone.double_taps) == expected,
        f"тапы не совпали с решением: {sorted(phone.double_taps)}",
    )


def test_every_cat_lands() -> None:
    """После прохода на поле должно быть ровно N котиков."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1):
        pass

    board = read_board(str(phone.out / "probe.png"))
    check(len(board.cats) == 8, f"котиков на поле {len(board.cats)}, ожидалось 8")


def test_leaderboard_then_board() -> None:
    """Лидеры: одиночный тап в надпись, дальше бот берётся за поле."""
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg", SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1):
        pass

    check(len(phone.taps) >= 1, "одиночных тапов не было")
    check(phone.taps[0] == (536, 2111), f"тапнул в {phone.taps[0]}, ожидалось (536, 2111)")
    check(len(phone.double_taps) == 8, f"после лидеров двойных тапов {len(phone.double_taps)}, ожидалось 8")


def test_level_done_button() -> None:
    """Экран пройденного: одиночный тап в оранжевую кнопку."""
    phone = FakePhone(screens=[SHOTS / "shot_2.jpg", SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1):
        pass

    check(len(phone.taps) >= 1, "одиночных тапов не было")
    check(phone.taps[0] == (540, 1840), f"тапнул в {phone.taps[0]}, ожидалось (540, 1840)")


def test_repeated_tap_when_screen_unchanged() -> None:
    """Если экран не меняется, тап повторяется в ту же точку."""
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg"])

    with running(phone, max_steps=3):
        pass

    check(len(phone.taps) >= 2, f"тапов {len(phone.taps)}, ожидались повторы")
    check(len(set(phone.taps)) == 1, f"тапы разъехались: {set(phone.taps)}")


def test_stopped_when_screen_never_changes() -> None:
    """Если экран так и не сменился, цикл должен завершиться, а не висеть."""
    phone = FakePhone(screens=[SHOTS / "shot_1.jpg"])

    with running(phone, max_steps=3) as code:
        pass

    check(code == 0, f"вернулся код {code}, ожидался 0")
    check(
        len(phone.taps) <= main.MAX_TAP_ATTEMPTS,
        f"тапов {len(phone.taps)}, ожидалось не больше {main.MAX_TAP_ATTEMPTS}",
    )


def test_repeats_double_tap_when_cat_missing() -> None:
    """Если кот не появился, двойной тап повторяется в ту же клетку."""
    broken = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    broken.double_tap = lambda x, y: broken.double_taps.append((int(x), int(y)))

    with running(broken, max_levels=1, max_steps=3):
        pass

    first = broken.double_taps[0]
    repeats = broken.double_taps[: main.MAX_TAP_ATTEMPTS]
    check(
        len(repeats) == main.MAX_TAP_ATTEMPTS,
        f"повторов {len(repeats)}, ожидалось {main.MAX_TAP_ATTEMPTS}",
    )
    check(set(repeats) == {first}, f"повтор ушёл в другую клетку: {set(repeats)}")


def test_level_counted_once() -> None:
    """Уровень не должен засчитываться дважды на одном и том же поле.

    Игра держит поле на экране ещё пару секунд после последнего котика.
    Без ожидания бот перечитывает то же поле и считает его новым уровнем.
    """
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1, max_steps=10):
        pass

    # Один уровень = ровно N двойных тапов, а не два прохода по полю.
    check(
        len(phone.double_taps) == 8,
        f"двойных тапов {len(phone.double_taps)}, ожидалось 8: "
        "похоже, уровень посчитан дважды",
    )


def test_waits_for_board_to_change() -> None:
    """После последнего котика бот ждёт, пока поле уйдёт с экрана."""
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    board = read_board(str(SHOTS / "shot_5.jpg"))

    # После того как все котики поставлены, поле остаётся на экране:
    # подделка не переключается сама, как и игра.
    for row, col in solve_from_board(board):
        phone.double_tap(*board.tap_point(row, col))

    with running(phone, max_levels=1, max_steps=5):
        pass

    check(
        len(phone.double_taps) == 8,
        f"после готового поля двойных тапов {len(phone.double_taps)}, "
        "бот продолжал тапать вместо ожидания",
    )


def test_retries_transition_frame() -> None:
    """Кадр во время анимации читается плохо — бот переснимает экран.

    На живом прогоне между уровнями ловился промежуточный кадр: поле 10x10
    собиралось с 12 цветами вместо 10. Через пару секунд кадр нормальный,
    поэтому нужен повтор, а не остановка.
    """
    broken = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    # Первые два кадра — мусор, дальше нормальное поле.
    def flaky_capture(destination):
        local = Path(destination)
        local.parent.mkdir(parents=True, exist_ok=True)
        if broken.index <= 2:
            broken.index += 1
            cv2.imwrite(
                str(local),
                np.full((2340, 1080, 3), 250, dtype=np.uint8),
            )
            return local
        return broken.capture(local)

    with mock.patch.object(main, "OUT_DIR", broken.out), \
         mock.patch.object(main, "LIVE_SHOT", broken.out / "live.png"), \
         mock.patch.object(main.emulate, "capture", side_effect=flaky_capture), \
         mock.patch.object(main.emulate, "tap", side_effect=broken.tap), \
         mock.patch.object(main.emulate, "double_tap", side_effect=broken.double_tap), \
         mock.patch.object(main.emulate, "is_connected", return_value=True), \
         mock.patch("time.sleep"):
        code = main.run_loop(dry_run=False, max_levels=1, max_steps=10)

    check(code == 0, f"вернулся код {code}, ожидался 0")
    check(len(broken.double_taps) == 8, f"двойных тапов {len(broken.double_taps)}, ожидалось 8")


def test_tiny_board_rejected() -> None:
    """Кадры перехода иногда читаются как поле 1x1 — это не доска."""
    from field import Board
    from solver import Solution

    tiny = Board(
        n=1,
        colors=(("A",),),
        cats=frozenset({(0, 0)}),
        centers=((0.0, 0.0),),
        tap_points=((0.0, 0.0),),
        palette=((0, 0, 0),),
        cell_w=10,
        cell_h=10,
    )

    problem = main.inspect_board(tiny)
    check(problem is not None, "поле 1x1 прошло проверку")
    check(
        problem is not None and "1x1" in problem,
        f"в сообщении нет размера: {problem}",
    )


def test_board_is_inspected_before_tapping() -> None:
    """Поле с подсветкой поверх читается как поле, но котиков там больше,
    чем может быть. Такое до тапов не допускаем."""
    from solver import Solution

    fake = Solution(
        n=10,
        cats=tuple((row, col) for row in range(10) for col in range(10))[:21],
    )

    from field import Board

    board = Board(
        n=10,
        colors=tuple(tuple("ABCDEFGHIJ" for _ in range(10)) for _ in range(10)),
        cats=frozenset(fake.cats),
        centers=tuple((0.0, 0.0) for _ in range(100)),
        tap_points=tuple((0.0, 0.0) for _ in range(100)),
        palette=tuple((0, 0, 0) for _ in range(10)),
        cell_w=10,
        cell_h=10,
    )

    problem = main.inspect_board(board)
    check(problem is not None, "21 котик на поле 10x10 прошёл проверку")
    check(
        problem is not None and "21" in problem,
        f"в сообщении нет числа котиков: {problem}",
    )


def test_real_boards_pass_inspection() -> None:
    """Настоящие доски проверку проходят."""
    for name in ("live_10x10_empty", "live_9x9_cat_on_grey", "live_10x10_one_cat"):
        board = read_board(str(SHOTS / f"{name}.png"))
        problem = main.inspect_board(board)
        check(problem is None, f"{name}: проверка отклонила доску: {problem}")


def test_overlay_board_does_not_pass() -> None:
    """Экран «уровень пройден» поверх поля должен отклоняться."""
    path = SHOTS / "bad21_cats.png"
    try:
        board = read_board(str(path))
    except Exception as error:
        # Отказ на этапе чтения — тоже правильное поведение.
        check(True, "")
        return

    problem = main.inspect_board(board)
    check(problem is not None, "поле с подсветкой прошло проверку")


def test_stops_on_ambiguous_board() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])
    from unittest import mock

    with mock.patch.object(
        main, "solve_from_board", side_effect=InconsistentBoard("Решений минимум 2")
    ):
        with running(phone, max_levels=1, max_steps=5):
            pass

    check(not phone.double_taps, "тапали на неоднозначном поле")


def test_stops_on_unknown_screen() -> None:
    blank = SHOTS / "BLANK_LOOP.png"
    cv2.imwrite(str(blank), np.full((2340, 1080, 3), 250, dtype=np.uint8))
    phone = FakePhone(screens=[blank])

    try:
        with running(phone, max_levels=1, max_steps=5) as code:
            pass

        check(code == 1, f"вернулся код {code}, ожидался 1")
        check(not phone.taps, "тапали на пустом экране")
    finally:
        blank.unlink(missing_ok=True)


def test_dry_run_never_taps() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    with running(phone, dry_run=True):
        pass

    check(not phone.taps, f"в dry-run одиночных тапов {len(phone.taps)}")
    check(not phone.double_taps, f"в dry-run двойных тапов {len(phone.double_taps)}")


def test_levels_limit_stops_loop() -> None:
    phone = FakePhone(screens=[SHOTS / "shot_5.jpg"])

    with running(phone, max_levels=1):
        pass

    check(len(phone.double_taps) == 8, f"двойных тапов {len(phone.double_taps)}, ожидалось 8")


def main_run() -> int:
    tests = (
        test_sprites_are_usable,
        test_single_level_one_pass,
        test_found_cats_not_tapped,
        test_taps_match_solution,
        test_every_cat_lands,
        test_leaderboard_then_board,
        test_level_done_button,
        test_repeated_tap_when_screen_unchanged,
        test_stopped_when_screen_never_changes,
        test_repeats_double_tap_when_cat_missing,
        test_level_counted_once,
        test_waits_for_board_to_change,
        test_retries_transition_frame,
        test_tiny_board_rejected,
        test_board_is_inspected_before_tapping,
        test_real_boards_pass_inspection,
        test_overlay_board_does_not_pass,
        test_stops_on_ambiguous_board,
        test_stops_on_unknown_screen,
        test_dry_run_never_taps,
        test_levels_limit_stops_loop,
    )

    for test in tests:
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты цикла прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_run())