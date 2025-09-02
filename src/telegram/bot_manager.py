import logging
import threading
import asyncio
from typing import TYPE_CHECKING, Optional, Dict

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

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


    async def _cmd_start(self, message: Message, state: FSMContext = None):
        if not self._is_authorized_user(message):
            return

        if state:
            await state.clear()

        keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🚀 Начать парсинг"), KeyboardButton(text="📊 Статус")],
            [KeyboardButton(text="🔧 Ресурсы"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="❓ Помощь")]
        ], resize_keyboard=True)

        welcome_text = (
            "🤖 <b>Добро пожаловать в Ozon Parser!</b>\n\n"
            "Выберите действие из меню ниже:"
        )

        await message.reply(welcome_text, reply_markup=keyboard, parse_mode="HTML")


    async def _cmd_status(self, message: Message):
        await self._show_status(message)


    async def _show_status(self, message_or_query):
        if not self._is_authorized_user(message_or_query):
            return

        status = self.app_manager.get_status()

        status_text = f"📊 <b>Статус парсера</b>\n\n"
        status_text += f"🔄 Парсинг: {'🟢 Активен' if status['is_running'] else '🔴 Остановлен'}\n"
        status_text += f"👥 Активных пользователей: {status.get('active_users_count', 0)}\n"
        status_text += f"🤖 Telegram бот: 🟢 Активен\n"
        status_text += f"📦 Макс. товаров: {status['settings']['max_products']}\n"
        status_text += f"⚙️ Макс. воркеров: {status['settings']['max_workers']}\n"

        # Показываем информацию о ресурсках
        if status.get('total_active_users', 0) > 0:
            status_text += f"\n🔧 <b>Ресурсы:</b>\n"
            status_text += f"⚙️ Используется воркеров: {status.get('total_allocated_workers', 0)}/10\n"

        # Показываем результаты для текущего пользователя
        user_id = str(message_or_query.from_user.id)
        user_results = self.app_manager.get_user_results(user_id)

        if user_results:
            status_text += f"\n📈 <b>Ваши результаты:</b>\n"
            status_text += f"✅ Успешно: {user_results.get('successful_products', 0)}/{user_results.get('total_products', 0)}"
        elif status['last_results']:
            # Fallback для совместимости
            results = status['last_result']
            status_text += f"\n📈 <b>Последний результат:</b>\n"
            status_text += f"✅ Успешно: {results.get('successful_products')}/{results.get('total_products', 0)}"

        keyboard = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🔄 Обновить"), KeyboardButton(text="🏠 Главное меню")]
        ], resize_keyboard=True)

        await message_or_query.reply(status_text, reply_markup=keyboard, parse_mode="HTML")

    async def _show_resources_status(self, message_or_query):
        if not self._is_authorized_user(message_or_query):
            return

        try:
            from ..utils.resource_manager import resource_manager
            status = resource_manager.get_status()

            status_text = "🔧 <b>Статус ресурсов</b>\n\n"

            if status['total_active_users'] == 0:
                status_text += "😴 Нет активных пользователей\n"
                status_text += f"📊 Доступно воркеров: {resource_manager.MAX_TOTAL_WORKERS}\n"
            else:
                status_text += f"👥Активных пользователей: {status['total_active_users']}\n"
                status_text += f"⚙️ Используется воркеров: {status['total_allocated_workers']}/{resource_manager.MAX_TOTAL_WORKERS}\n\n"

                for user_id, session_info in status['sessions'].items():
                    user_display = f"User_{user_id[-4:]}" if len(user_id) > 4 else user_id
                    status_text += f"   👤<b>{user_display}</b>\n"
                    status_text += f"   📋 Этап: {session_info['stage']}\n"
                    status_text += f"   ⚙️ Воркеров: {session_info['workers']}\n"
                    status_text += f"   📈 Прогресс: {session_info['progress']}\n"
                    status_text += f"   ⏱ Время: {session_info['duration']}\n\n"

            status_text += f"\n📋 <b>Лимиты:</b>\n"
            status_text += f"• Макс воркеров всего: {resource_manager.MAX_TOTAL_WORKERS}\n"
            status_text += f"• Макс на пользователя: {resource_manager.MAX_WORKERS_PER_USER}\n"
            status_text += f"• Мин на пользователя: {resource_manager.MIN_WORKERS_PER_USER}\n"

        except Exception as e:
            status_text = f"❌ Ошибка получения статуса ресурсов: {e}"

        await message_or_query.reply(status_text, parse_mode="HTML")


    async def _cmd_settings(self, message: Message, state: FSMContext):
        await self._show_settings(message, state)


    async def _show_settings(self, message_or_query, state: FSMContext):
        if not self._is_authorized_user(message_or_query):
            return

        user_id = str(message_or_query.from_user.id)
        settings = self.db.get_user_settings(user_id)


    def _is_authorized_user(self, message_or_query) -> bool:
        user_id = str(message_or_query.from_user.id)
        if user_id not in self.user_ids:
            logger.warning(f"Неавторизованный пользователь {user_id} пытается использовать бота")
            return False
        return True








