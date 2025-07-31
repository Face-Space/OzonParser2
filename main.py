"""
Главный файл приложения Ozon Parser - запуск GUI
Запуск: python main.py
"""
import logging

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

    except Exception as e:
        print(f"❌Ошибка запуска GUI❌: {e}")

if __name__ == "__main__":
    main()