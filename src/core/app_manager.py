import threading

from ..config.settings import Settings



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
