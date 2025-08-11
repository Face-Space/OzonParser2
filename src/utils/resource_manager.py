import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


# Этот декоратор автоматически добавляет в класс полезные методы, например:
# __init__() — конструктор, который автоматически принимает и сохраняет поля,
# __repr__() — для удобного красивого вывода объекта,
# __eq__() — для сравнения объектов,
# и другие.
# Это очень удобно для создания классов, которые в основном хранят данные
@dataclass
class UserSession:
    user_id: str
    start_time: datetime
    current_stage: str   # 'links', 'products', 'sellers', 'idle'
    allocated_workers: int
    total_items: int
    processed_items: int = 0

class ResourceManager:
    '''Менеджер для динамического распределения воркеров между пользователями'''

    # Константы
    MAX_TOTAL_WORKERS = 15
    MAX_WORKERS_PER_USER = 5
    MIN_WORKERS_PER_USER = 2
    SESSION_TIMEOUT_MINUTES = 30

    def __init__(self):
        self._lock = threading.RLock()
        self._active_sessions: Dict[str, UserSession] = {}
        self._cleanup_thread = None
        self._start_cleanup_thread()
        logger.info(f"ResourceManager инициализирован: макс {self.MAX_TOTAL_WORKERS} воркеров, макс {self.MAX_WORKERS_PER_USER} на пользователя")


    def _start_cleanup_thread(self):
        '''Запускает поток для очистки устаревших сессий'''
        def cleanup_loop():
            while True:
                try:
                    self._cleanup_expired_session()
                    time.sleep(60)   # Проверяем каждую минуту
                except Exception as e:
                    logger.error(f"Ошибка в потоке очистки сессий: {e}")
                    time.sleep(60)

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()


    def start_parsing_session(self, user_id: str, stage: str, total_items: int) -> int:
        '''
        Начинает новую сессию парсинга для пользователя

        Args:
            user_id: ID пользователя
            stage: Этап парсинга ("links", "products", "sellers")
            total_items: Общее количество элементов для обработки

        Returns:
            Количество выделенных воркеров
        '''
        with self._lock:
            current_time = datetime.now()

            # Если у пользователя есть активная сессия, обновляем её
            if user_id in self._active_sessions:
                session = self._active_sessions[user_id]
                session.current_stage = stage
                session.total_items = total_items
                session.processed_items = 0
                # НЕ обновляем start_time, чтобы сохранить порядок пользователей
                logger.info(f"Обновлена сессия пользователя {user_id}: этап {stage}, {total_items} элементов")
            else:
                # Создаём новую сессию
                session = UserSession(
                    user_id=user_id,
                    start_time=current_time,
                    current_stage=stage,
                    allocated_workers=0,  # Будет установлено при перераспределении
                    total_items = total_items
                )
                self._active_sessions[user_id] = session
                logger.info(f"Создана новая сессия пользователя {user_id}: этап {stage}, {total_items} элементов")

        # ВСЕГДА перераспределяем воркеры в начале каждого этапа
        # Это гарантирует справедливое распределение на основе текущего количества активных пользователей
        self._redistribute_workers()

        allocated_workers = self._active_sessions[user_id].allocated_workers
        logger.info(f"Пользователь {user_id} получил {allocated_workers} воркеров для этапа {stage}"
                    f"(активных пользователей: {len(self._active_sessions)})")

        return allocated_workers


    def update_progress(self, user_id: str, processed_items: int):
        '''Обновляет прогресс пользователя'''
        with self._lock:
            if user_id in self._active_sessions:
                self._active_sessions[user_id].processed_items = processed_items


    def finish_parsing_session(self, user_id: str):
        '''Завершает сессию парсинга пользователя'''
        with self._lock:
            if user_id in self._active_sessions:
                del self._active_sessions[user_id]
                logger.info(f"Завершена сессия пользователя {user_id}")
                # Перераспределяем воркеры между оставшимися пользователями
                self._redistribute_workers()


    def get_active_users_count(self) -> int:
        """Возвращает количество активных пользователей"""
        with self._lock:
            return len(self._active_sessions)


    def get_user_workers(self, user_id: str) -> int:
        """Возвращает количество воркеров для пользователя"""
        with self._lock:
            if user_id in self._active_sessions:
                return self._active_sessions[user_id].allocated_workers
            return self.MIN_WORKERS_PER_USER

    def get_status(self) -> Dict:
        """Возвращает статус всех активных сессий"""
        with self._lock:
            status = {
                'total_active_users': len(self._active_sessions),
                'total_allocated_workers': sum(session.allocated_workers for session in self._active_sessions.values()),
                'sessions': {}
            }
