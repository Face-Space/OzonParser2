"""
Главный файл приложения Ozon Parser - запуск GUI
Запуск: python main.py
"""
from src.utils.logger import setup_logging


def main():
    # Запуск GUI для управления телеграмм ботом
    try:
        # настройка логгирования
        setup_logging()
    except Exception as e:
        print(f"❌Ошибка запуска GUI❌: {e}")

if __name__ == "__main__":
    main()