"""Meowdoku: чтение поля, решение и игровой цикл.

Модули пакета:
    config          все пороги и настройки
    logging_setup   логгер
    domain          Cell, CellBox, ScreenKind
    field           чтение поля: CellDetector, ColorReader, CatDetector, BoardReader
    solver          Solver — поиск единственной расстановки
    device          AdbDevice — скриншоты и тапы через adb
    screens         определение экрана: ScreenClassifier и наследники Screen
    annotate        Annotator — разбор поверх скриншота
    game            игровой цикл: BoardValidator, LevelPlayer, GameBot
"""