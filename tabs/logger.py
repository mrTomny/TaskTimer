import logging
from logging.handlers import RotatingFileHandler
import os
import sys

def setup_logger():
    # --- СТАЛО: Локальный импорт решает проблему циклического импорта! ---
    from tabs.utils import get_app_dir 
    
    logger = logging.getLogger("TaskTimer")
    logger.setLevel(logging.DEBUG) # Ловим всё от DEBUG и выше

    # ЗАЩИТА ОТ ДУБЛИРОВАНИЯ: если хендлеры уже добавлены, не добавляем их заново
    if logger.handlers:
        return logger

    # Формат сообщения: Время - Уровень - Файл - Сообщение
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s] - %(message)s')

    # Решение проблемы с путем: берем базовую директорию из нашей утилиты
    app_dir = get_app_dir()
    log_file = os.path.join(app_dir, "app.log")

    # Обработчик для записи в файл (максимум 5 МБ, храним 2 старых бэкапа)
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Решение проблемы с StreamHandler: выводим в консоль только если она существует
    if sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

log = setup_logger()

def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """
    Эта функция будет автоматически вызываться при любой ошибке,
    из-за которой программа собирается "вылететь".
    """
    # Игнорируем стандартное прерывание с клавиатуры (Ctrl+C)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Записываем полный след ошибки (Traceback) в наш лог!
    log.critical("НЕОБРАБОТАННАЯ ОШИБКА (КРАШ ПРОГРАММЫ):", exc_info=(exc_type, exc_value, exc_traceback))

# Подменяем стандартный системный обработчик на наш
sys.excepthook = handle_unhandled_exception