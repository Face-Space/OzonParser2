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
            if user_id and user_id in self.active_parsing_users:
                logger.warning(f"Пользователь {user_id} уже запустил парсинг")
                return False

        # Добавляем пользователя в активные
        if user_id:
            self.active_parsing_users.add(user_id)

        # Устанавливаем глобальный флаг для первого пользователя
        if not self.is_running:
            self.stop_event.clear()
            self.is_running = True

        try:
            # запускаем парсинг в отдельном потоке
            parsing_thread = threading.Thread(
                target=self._parsing_task_wrapper,
                args=(category_url, selected_fields, user_id),
                daemon=True
            )
            parsing_thread.start()
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска парсинга для пользователя {user_id}: {e}")
            # Убираем пользователя из активных при ошибке
            with self.parsing_lock:
                if user_id and user_id in self.active_parsing_users:
                    self.active_parsing_users.remove(user_id)
                # Если это был последний пользователь, сбрасываем глобальный флаг
                if not self.active_parsing_users:
                    self.is_running = False
            return False

    # _ - это функция предназначена для внутреннего использования и не должна использоваться
    # напрямую за пределами данного класса или модуля
    def _parsing_task_wrapper(self, category_url: str, selected_fields: list = None, user_id: str = None):
        '''Wrapper для парсинга с правильной очисткой ресурсов'''
        try:
            self._parsing_task(category_url, selected_fields, user_id)
        except Exception as e:
            logger.error(f"Ошибка в парсинге для пользователя {user_id}: {e}")
        finally:
            # Убираем пользователя из активных
            with self.parsing_lock:
                if user_id and user_id in self.active_parsing_users:
                    self.active_parsing_users.remove(user_id)
                    logger.info(f"Пользователь {user_id} завершил парсинг")

                # Если это был последний пользователь, сбрасываем глобальный флаг
                if not self.active_parsing_users:
                    self.is_running = False
                    logger.info("Все пользователи завершили парсинг")

    def stop_parsing(self, user_id: str = None):
        '''Останавливает парсинг для конкретного пользователя или всех'''

