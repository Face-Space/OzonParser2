import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


def setup_logging(log_level="INFO", log_dir=None):

    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
        # Создаётся объект Path, представляющий путь к текущему файлу
        # Атрибут .parent у объекта Path возвращает путь к родительской папке данного файла или папки
        # "logs" — это имя папки, которую мы хотим добавить

    log_dir = Path(log_dir)
    log_dir.mkdir(exist_ok=True)
    # Метод .mkdir() создает каталог (папку) по пути, на который указывает log_dir
    # Параметр exist_ok=True говорит: Если папка уже есть — не выдавать ошибку, просто продолжить работу

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Форматтер (Formatter) в модуле logging отвечает за формат записи логов —
    # как будет выглядеть каждая строчка лога

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # В модуле logging функция getLogger() возвращает объект логгера (Logger).
    # Если вызвать getLogger() без аргументов, будет получен корневой (root) логгер.
    # Корневой логгер — это главный логгер по умолчанию, через который проходят все сообщения, если не используются другие дочерние логгеры.
    # Этот объект позволяет настраивать поведение логирования для всего приложения, например, уровень логирования, обработчики, форматтеры и т.п.

    # Метод setLevel() задаёт минимальный уровень важности сообщений, которые будут обрабатываться логгером
    # getattr(logging, 'INFO') возвращает значение константы из модуля logging, соответствующее уровню

    root_logger.handlers.clear()

    # root_logger.handlers - список всех активных обработчиков, которые "слушают" этот логгер и обрабатывают все лог-сообщения.
    # Обработчики (Handler) отвечают за то, куда именно отправляются логи: в файл, на консоль, по сети.
    # Здесь удаляется список всех обработчиков, которые были прикреплены к корневому логгеру.

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Метод .addHandler(handler) добавляет этот обработчик к логгеру, чтобы он начал получать и обрабатывать все сообщения,
    # которые логгер будет выдавать

    log_file = log_dir / f"ozon_parser2_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024, # 10MB
        backupCount=5,
        encoding='utf-8'
    )

    # Создаёт объект RotatingFileHandler, который пишет логи в файл log_file.
    # Лог-файл ограничен по размеру 10 МБ.
    # Когда файл достигает 10 МБ, текущий файл переименовывается в файл с индексом, а лог пишется в новый пустой файл.
    # Хранится максимум 5 предыдущих файлов с логами, старые удаляются.

    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)







