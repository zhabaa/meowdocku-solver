"""Тесты логгера и общих типов.

Запуск: .venv/bin/python test_logging.py
"""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from domain import Cell, CellBox, ScreenKind
from logging_setup import LOGGER_NAME, get_logger, setup_logging

failures: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def test_writes_to_file() -> None:
    with TemporaryDirectory() as folder:
        log_file = Path(folder) / "nested" / "bot.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        logger.info("строка для проверки")
        for handler in logger.handlers:
            handler.flush()

        check(log_file.exists(), f"лог не создан: {log_file}")
        text = log_file.read_text(encoding="utf-8")
        check("строка для проверки" in text, "сообщение не попало в файл")
        check("INFO" in text, "в файле нет уровня сообщения")


def test_console_quiet_without_verbose() -> None:
    """Без --verbose в консоль должно уходить только WARNING и хуже."""
    with TemporaryDirectory() as folder:
        logger = setup_logging(verbose=False, log_file=Path(folder) / "bot.log")

        console_levels = [
            handler.level
            for handler in logger.handlers
            if not isinstance(handler, logging.FileHandler)
        ]
        check(
            console_levels == [logging.INFO],
            f"уровень консоли {console_levels}, ожидался INFO (в файле всё равно DEBUG)",
        )


def test_console_verbose() -> None:
    with TemporaryDirectory() as folder:
        logger = setup_logging(verbose=True, log_file=Path(folder) / "bot.log")

        console_levels = [
            handler.level
            for handler in logger.handlers
            if not isinstance(handler, logging.FileHandler)
        ]
        check(console_levels == [logging.DEBUG], f"уровень консоли {console_levels}, ожидался DEBUG")


def test_file_always_keeps_debug() -> None:
    """В файл пишется всё, даже когда консоль молчит."""
    with TemporaryDirectory() as folder:
        log_file = Path(folder) / "bot.log"
        logger = setup_logging(verbose=False, log_file=log_file)

        get_logger("field").debug("тихая отладка")
        for handler in logger.handlers:
            handler.flush()

        check("тихая отладка" in log_file.read_text(encoding="utf-8"), "DEBUG не попал в файл")


def test_no_duplicate_handlers() -> None:
    """Повторный setup_logging не должен дублировать записи."""
    with TemporaryDirectory() as folder:
        log_file = Path(folder) / "bot.log"

        setup_logging(log_file=log_file)
        logger = setup_logging(log_file=log_file)

        check(
            len(logger.handlers) == 2,
            f"обработчиков {len(logger.handlers)}, ожидалось 2 (файл и консоль)",
        )

        logger.info("одна запись")
        for handler in logger.handlers:
            handler.flush()

        occurrences = log_file.read_text(encoding="utf-8").count("одна запись")
        check(occurrences == 1, f"запись попала в файл {occurrences} раз, ожидалась одна")


def test_logger_names() -> None:
    check(get_logger().name == LOGGER_NAME, f"имя корневого логгера {get_logger().name}")
    check(get_logger("field").name == f"{LOGGER_NAME}.field", "имя логгера модуля неверно")


def test_cell_kind() -> None:
    check(ScreenKind.BOARD == "board", "ScreenKind не сравнивается со строкой")
    check(Cell(1, 2) == Cell(1, 2), "Cell не сравнивается по значению")
    check(Cell(1, 2) != Cell(2, 1), "разные клетки считаются равными")
    check(str(Cell(3, 7)) == "(3,7)", f"Cell печатается как {Cell(3, 7)}")
    check(
        sorted([Cell(3, 1), Cell(1, 5), Cell(1, 2)]) == [Cell(1, 2), Cell(1, 5), Cell(3, 1)],
        "Cell не сортируется по строке и столбцу",
    )


def test_cell_box() -> None:
    box = CellBox(left=10, top=20, width=100, height=110)

    check(box.center_x == 60, f"центр по X {box.center_x}, ожидался 60")
    check(box.center_y == 75, f"центр по Y {box.center_y}, ожидалось 75")
    check(box.smaller_side == 100, f"меньшая сторона {box.smaller_side}, ожидалось 100")
    check(box.contains(50, 60), "точка внутри клетки не найдена")
    check(not box.contains(5, 60), "точка слева засчитана как внутри")
    check(not box.contains(50, 5), "точка сверху засчитана как внутри")


def main() -> int:
    for test in (
        test_writes_to_file,
        test_console_quiet_without_verbose,
        test_console_verbose,
        test_file_always_keeps_debug,
        test_no_duplicate_handlers,
        test_logger_names,
        test_cell_kind,
        test_cell_box,
    ):
        test()
        print(f"{test.__name__}: выполнен")

    if failures:
        print(f"\nПРОВАЛЕНО ({len(failures)}):")
        for message in failures:
            print(f"  - {message}")
        return 1

    print("\nВсе тесты логгера и типов прошли")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
