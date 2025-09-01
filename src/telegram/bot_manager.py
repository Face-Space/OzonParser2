import logging
import threading
import asyncio
from typing import TYPE_CHECKING, Optional, Dict

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import StatesGroup, State

if TYPE_CHECKING:
    from ..core.app_manager import AppManager
    #  условие, которое будет истинным только во время статической типизации (то есть, когда проверяется код
    #  средствами типа mypy). Во время обычного запуска программы это условие ложно, и тело этого блока не исполняется

    # Этот импорт помогает избежать проблем с циклическими зависимостями, так как при обычном запуске блока кода внутри
    # if TYPE_CHECKING: не будет выполняться, и импорт не будет происходить.

    #  код внутри блока if TYPE_CHECKING: виден и исполняется только инструментами проверки типов, а не самим Python
    #  при запуске. Статическая типизация происходит именно в момент работы такого инструмента (mypy или аналогичных),
    #  а не в runtime

logger = logging.getLogger()

class ParsingStates(StatesGroup):
    waiting_for_url = State()
    waiting_for_count = State()
    settings_menu = State()
    waiting_for_default_count = State()

FIELD_NAMES = {
    'article': 'Артикул',
    'name': 'Название товара',
    'seller_name': 'Продавец',
    'company_name': 'Название компании',
    'inn': 'ИНН',
    'card_price': 'Цена карты',
    'price': 'Цена',
    'original_price': 'Старая цена',
    'product_url': 'Ссылка на товар',
    'image_url': 'Ссылка на изображение',
    'orders_count': 'Количество заказов',
    'reviews_count': 'Количество отзывов',
    'average_rating': 'Рейтинг',
    'working_time': 'Работает с'
}

class TelegramBotManager:

    def __init__(self, bot_token: str, user_ids: list, app_manager: 'AppManager'):
        self.bot_token = bot_token
        self.user_ids = user_ids  # Список разрешенных User ID
        self.app_manager = app_manager
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()
        self.is_running = False
        self.bot_thread: Optional[threading.Thread] = None
        self.db = Database()
        self.user_data: Dict[str, dict] = {}
        self.parsing_user_id = None

        self._register_handlers()


    def start(self) -> bool:
        try:
            # Запускаем бота в отдельном потоке
            self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self.bot_thread.start()

            # Даём боту время на инициализацию
            import time
            time.sleep(2)

            if self.is_running:
                # Создаём отдельный поток для отправки стартового сообщения
                notification_thread = threading.Thread(
                    target=self._send_startup_notification,
                    daemon=True
                )
                notification_thread.start()
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"Ошибка запуска Telegram бота: {e}")
            return False


    def _send_startup_notification(self):
        """Отправляет уведомление о запуске в отдельном потоке"""
        try:
            # Создаём новый бот для отправки сообщения
            # Это избегает проблем с asyncio
            temp_bot = Bot(token=self.bot_token)

            async def send_and_close():
                try:
                    # Отправляем уведомление всем разрешенным пользователям
                    for user_id in self.user_ids:
                        await temp_bot.send_message(chat_id=user_id,
                                                    text="🤖 Ozon Parser бот запущен и готов к работе!")
                finally:
                    await temp_bot.session.close()

            # Запускаем в новом цикле событий
            asyncio.run(send_and_close())

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о запуске: {e}")


    def _run_bot(self):
        try:
            self._is_running = True
            asyncio.run(self.dp.start_polling(self.bot))

        except Exception as e:
            logger.error(f"Ошибка работы Telegram бота: {e}")
            self.is_running = False


    def _register_handlers(self):
        self.dp.message.register(self._cmd_start, Command('start'))
        self.dp.message.register(self._cmd_status, Command('status'))
        self.dp.message.register(self._cmd_settings, Command('settings'))
        self.dp.message.register(self._cmd_help, Command('help'))

        self.dp.callback_query.register(self._handle_callback)
        self.dp.message.register(self._handle_url_input, StateFilter(ParsingStates.waiting_for_url))
        self.dp.message.register(self._handle_count_input, StateFilter(ParsingStates.waiting_for_count))
        self.dp.message.register(self._handle_default_count_input, StateFilter(ParsingStates.waiting_for_default_count))
        self.dp.message.register(self._handle_message)









