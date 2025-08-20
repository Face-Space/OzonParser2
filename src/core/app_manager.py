import logging
import threading
import time
from typing import Optional

from ..config.settings import Settings
from ..parsers.product_parser import OzonProductParser
from ..parsers.link_parser import OzonLinkParser
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
        #  нужен для сигнализации между потоками — один поток "сигналит" событие с помощью set(),
        #  а другие потоки "ждут" этого сигнала через wait() для перехода к следующему этапу работы
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
        """Wrapper для парсинга с правильной очисткой ресурсов"""
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
        """Останавливает парсинг для конкретного пользователя или всех"""
        with self.parsing_lock:
            if user_id:
                # Останавливаем парсинг для конкретного пользователя
                if user_id in self.active_parsing_users:
                    self.active_parsing_users.remove(user_id)
                    logger.info(f"Остановлен парсинг для пользователя {user_id}")

            else:
                # Останавливаем все парсинги
                self.active_parsing_users.clear()
                logger.info("Остановлен парсинг для всех пользователей")

            # Если нет активных пользователей, сбрасываем глобальный флаг
            if not self.active_parsing_users:
                self.stop_event.set()
                # Метод .set() меняет этот флаг на True, тем самым сигнализируя, что событие произошло
                # Таким образом, событие служит простым механизмом для синхронизации потоков: один поток вызывает
                # set(), сигнализируя об этом, и другие потоки, ждущие этого события через wait(), продолжают работу
                self.is_running = False

    def _parsing_task(self, category_url: str, selected_fields: list = None, user_id: str = None):
        start_time = time.time()
        link_parser = OzonLinkParser(category_url, self.settings.MAX_PRODUCTS, user_id)

        success, product_links = link_parser.start_parsing()

        if self.stop_event.is_set():
            return

        if not success or not product_links:
            logger.error("Не удалось собрать ссылки товаров")
            return

        if self.stop_event.is_set():
            return

        product_parser = OzonProductParser(self.settings.MAX_WORKERS, user_id)
        product_results = product_parser.parse_products(product_links)

        # Принудительно закрываем все воркеры продуктов перед началом парсинга продавцов
        product_parser.cleanup()

        if self.stop_event.is_set():
            return

        seller_ids = []
        for product in product_results:
            if product.seller_id and product.success:
                seller_ids.append(product.seller_id)

        unique_seller_ids = list(set(seller_ids))


        seller_results = []
        if unique_seller_ids:
            logger.info(f"Начинаем парсинг {len(unique_seller_ids)} продавцов после закрытия всех воркеров продуктов.")
            seller_parser = OzonSellerParser(self.settings.MAX_WORKERS, user_id)
            seller_results = seller_parser.parse_sellers(unique_seller_ids)






