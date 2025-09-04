"""
Главный файл приложения Ozon Parser - запуск GUI
Запуск: python main.py
"""
import sys
import logging
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))
# В Python sys.path — это список строк, где каждая строка — путь к каталогу, в котором
# интерпретатор ищет модули для импорта
# sys.path.insert(0, ...) — добавляет этот путь в начало списка путей поиска модулей

# Эта строчка гарантирует, что директория, где расположен текущий файл, будет первой
# в списке путей поиска модулей Python


from src.core.app_manager import AppManager
from src.gui.main_window import MainWindow
from src.utils.logger import setup_logging
from src.config.settings import Settings


def main():
    # Запуск GUI для управления телеграмм ботом
    try:
        # настройка логгирования
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Запуск Telegram Bot Manager GUI")

        # __name__ — это специальная переменная в Python, которая содержит имя текущего модуля или "__main__",
        # если скрипт запускается как основная программа.
        # Использование __name__ при создании логгера помогает структурировать логи, отражая, из какого именно
        # модуля они пришли. Это удобно в больших проектах и при отладке

        # загрузка настроек
        settings = Settings()

        # создание менеджера приложения
        app_manager = AppManager(settings)

        # Создание и запуск GUI
        gui = MainWindow(app_manager)
        gui.run()


    except Exception as e:
        print(f"❌Ошибка запуска GUI❌: {e}")

if __name__ == "__main__":
    main()