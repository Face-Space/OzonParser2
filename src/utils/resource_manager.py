import logging
from dataclasses import dataclass
from datetime import datetime

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




