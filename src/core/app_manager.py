import logging
import threading
from typing import Optional

from ..config.settings import Settings
from ..telegram.bot_manager import TelegramBotManager


logger = logging.getLogger(__name__)
# __name__ — это встроенная переменная в Python, которая содержит
# полное имя текущего модуля в пространстве имён пакетов
# это удобно, чтобы логи автоматически показывали, из какого модуля они пришли,
# и чтобы можно было настроить разные уровни логирования для разных модулей

class AppManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.is_running = False  # Глобальный флаг для совместимости
        self.active_parsing_users = set()  # Множество активных пользователей
        self.parsing_lock = threading.RLock()
        #  эта блокировка будет использоваться для управления доступом к парсингу
        #  (например, чтобы не запускать несколько потоков парсинга одновременно или защитить данные
        #  от одновременного доступа)
        self.stop_event = threading.Event()
        # threading.Event()  служит индикатором, который можно "поднять", чтобы сообщить другим потокам
        # — "хватит работать, нужно остановиться"
        self.last_results = {}  # Глобальные результаты для совместимости
        self.user_results = {}  # Результаты по пользователям: {user_id: results}
        self.telegram_bot: Optional[TelegramBotManager] = None
        # : Optional[TelegramBotManager] — это аннотация типа. Она указывает, что переменная telegram_bot
        # может содержать либо объект типа TelegramBotManager, либо значение None

    def start_parsing(self, category_url: str, selected_fields: list = None, user_id: str = None) -> bool:
        with self.parsing_lock:
            # Проверяем, не парсит ли уже этот пользователь


