import logging
from pathlib import Path
import sys
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_config_path() -> Path:
    """Возвращает путь к файлу конфигурации"""
    if getattr(sys, "frozen", False):
        # Если приложение скомпилировано (PyInstaller)

        # Используется функция getattr для проверки, существует ли у модуля sys атрибут frozen.
        # Атрибут frozen устанавливается, если программа запущена в форме скомпилированного приложения
        # (например, созданного с помощью PyInstaller) т.е. исходный код программы на Python был преобразован
        # в отдельный исполняемый файл (например, .exe на Windows)


        config_path = Path(sys.executable).parent / "config.txt"
        # sys.executable — путь к исполняемому файлу (самому .exe или бинарнику).
        # Path(sys.executable) — превращает путь в объект Path для удобной работы.
        # .parent — берёт каталог, в котором лежит исполняемый файл.
        # / "config.txt" — объединяет путь к папке с именем файла "config.txt".
        # В итоге config_path — это путь к файлу "config.txt" в той же папке, где находится исполняемый файл программы.
    else:
        # Если запущено из исходников
        config_path = Path(__file__).parent.parent.parent / "config.txt"

    return config_path

def read_config() -> Dict[str, str]:
    """Читает файл конфигурации и возвращает словарь с настройками"""
    config_path = get_config_path()
    logger.info(f"Поиск config.txt по пути: {config_path}")

    config = {}

    if not config_path.exists():
        logger.warning(f"config.txt не найден по пути: {config_path}")
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split("=", 1)
                    config[key] = value

    except Exception as e:
        logger.error(f"Ошибка чтения config.txt")

    return config


def write_config(new_config: Dict[str, Any]) -> bool:
    """Записывает настройки в файл конфигурации"""
    config_path = get_config_path()

    try:
        # Сначала читаем существующий файл, чтобы сохранить другие настройки
        existing_config = read_config()

        # Обновляем существующие настройки новыми
        for key, value in new_config.items():
            existing_config[key] = str(value)

        with open(config_path, 'w', encoding="utf-8") as f:
            for key, value in existing_config.items():
                f.write(f"{key}={value}\n")
        return True

    except Exception as e:
        logger.error(f"Ошибка записи в config.txt: {e}")
        return False










