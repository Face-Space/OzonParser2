import logging
import threading
import time
from typing import Optional

from ..config.settings import Settings
from ..parsers.product_parser import OzonProductParser
from ..parsers.link_parser import OzonLinkParser
from ..parsers.seller_parser import OzonSellerParser
from ..telegram.bot_manager import TelegramBotManager
from ..utils.excel_exporter import ExcelExporter


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
            # Закрываем воркеры продавцов после завершения
            seller_parser.cleanup()

        if self.stop_event.is_set():
            return

        # Метод is_set() возвращает True, если это событие было установлено (set), то есть произошло некоторое
        # условие или сигнал для остановки.

        seller_data = {}
        for seller in seller_results:
            if seller.success:
                seller_data[seller.seller_id] = seller

        end_time = time.time()
        total_time = end_time - start_time
        successful_products = len([p for p in product_results if p.success])
        failed_products = len([p for p in product_results if not p.success])
        avg_time_per_product = total_time / len(product_results) if product_results else 0

        # Сохраняем результаты для конкретного пользователя
        user_results = {
            'links': product_links,
            'products': product_results,
            'sellers': seller_results,
            'category_url': category_url,
            'total_products': len(product_results),
            'successful_products': successful_products,
            'failed_products': failed_products,
            'total_sellers': len(seller_results),
            'successful_sellers': len([s for s in seller_results if s.success]),
            'output_folder': getattr(link_parser, 'output_folder', 'unknown'),
            'seller_data': seller_data,
            'selected_fields': selected_fields,
            'parsing_stats': {
                'total_time': total_time,
                'successful_products': successful_products,
                'failed_products': failed_products,
                'average_time_per_product': avg_time_per_product
            }
        }

        # Сохраняем результаты для пользователя
        if user_id:
            self.user_results[user_id] = user_results

        # Обновляем глобальные результаты для совместимости
        self.last_results = user_results

        self._save_results_to_file(user_id)
        self._export_to_excel(user_id)
        self._send_report_to_telegram(user_id)


    def _save_results_to_file(self, user_id: str = None):
        try:
            import json
            from datetime import datetime
            from pathlib import Path

            folder_name = self.last_results.get('output_folder', 'unknown')
            filename = f"category_{folder_name}.json"
            current_timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")

            output_dir = self.settings.OUTPUT_DIR / folder_name
            filepath = output_dir / filename

            # Получаем результаты для конкретного пользователя
            results = self.user_results.get(user_id, self.last_results) if user_id else self.last_results

            save_data = {
                'timestamp': current_timestamp,
                'category_url': results.get('category_url', ''),
                'total_products': results.get('total_products', 0),
                'successful_products': results.get('successful_products', 0),
                'total_sellers': results.get('total_sellers', 0),
                'successful_sellers': results.get('successful_sellers', 0),
                'products': []
            }

            for product in results.get('products', []):
                product_url = ""
                for url in results.get('links', {}).keys():
                    if product.article in url:
                        product_url = url
                        break

                seller_info = results.get('seller_data', {}).get(product.seller_id, None)

                seller_data = {
                    'name': product.company_name,
                    'id': product.seller_id,
                    'link': product.seller_link,
                    'inn': '',
                    'company_name': ''
                }

                if seller_info:
                    company_name = seller_info.company_name.replace('\\"', '"').replace('\"', '"').replace('"', '"')

                    # .replace('\\"', '"') — заменяет последовательность из обратного слеша и двойной кавычки \" на просто двойную кавычку ".
                    # Обычно \" — это экранированная двойная кавычка в строках. Такая замена может использоваться,
                    # чтобы убрать лишнее экранирование.
                    # .replace('\"', '"') — заменяет (в данном коде эквивалент) повторяющуюся попытку заменить экранированную
                    # кавычку, но в Python в строковых литералах \" и " в пределах одинарных кавычек — одно и то же.
                    # replace('"', '"'), эта строка скорее избыточна или предусмотрена для ситуации, где
                    # экранированная кавычка передана иначе

                    seller_data.update({
                        'inn': seller_info.inn,
                        'company_name': company_name,
                        'orders_count': seller_info.orders_count,
                        'reviews_count': seller_info.reviews_count,
                        'working_time': seller_info.working_time,
                        'average_rating': seller_info.average_rating
                    })
                    # update - обновляет текущий словарь новыми или изменёнными парами ключ-значение

                if "name" in seller_data:
                    seller_data["name"] = seller_data['name'].replace('\\"', '"').replace('\"', '"').replace('"', '"')

                save_data['products'].append({
                    'article': product.article,
                    'name': product.name,
                    'seller': seller_data,
                    'image_url': product.image_url,
                    'card_price': product.card_price,
                    'price': product.price,
                    'original_price': product.original_price,
                    'product_url': product_url,
                    'success': product.success,
                    'error': product.error
                })

            with open(filepath, 'w', encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Ошибка сохранения результатов: {e}")


    def _export_to_excel(self, user_id: str = None):
        try:
            # Получаем результаты для конкретного пользователя
            results = self.user_results.get(user_id, self.last_results) if user_id else self.last_results

            folder_name = results.get('output_folder', 'unknown')
            output_dir = self.settings.OUTPUT_DIR / folder_name

            exporter = ExcelExporter(output_dir, f"category_{folder_name}")
            selected_fields = results.get('selected_fields', [])

            export_data = {'products': []}

            for product in results.get('products', []):
                product_url = ""



