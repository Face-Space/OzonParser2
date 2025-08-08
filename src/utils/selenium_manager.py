import logging
from selenium import webdriver
from typing import Optional

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium_stealth import stealth

logger = logging.getLogger(__name__)

class SeleniumManager:

    def __init__(self, headless=True):
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

    def create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()

        chrome_options.add_argument("--no-sandbox")
        # Песочница — это изолированная среда, которая повышает безопасность, но иногда в некоторых окружениях
        # (например, в Docker или на серверах) она вызывает проблемы. Отключение помогает заставить браузер
        # работать в таких средах.

        chrome_options.add_argument("--disable-dev-shm-usage")
        # Отключает использование общей мемори (shared memory) /dev/shm. В стандартных Linux-средах /dev/shm используется
        # для хранения временных файлов в оперативной памяти, но в некоторых контейнерах Docker или ограниченных средах
        # доступ к /dev/shm может быть ограничен. Этот параметр заставляет Chrome использовать диск вместо этой общей
        # памяти, что помогает избежать ошибок из-за нехватки ресурса

        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        # Отменяет работу функции Chrome (Blink — движок рендеринга), которая выдаёт, что браузер управляется
        # автоматизацией (например, Selenium). Это используется, чтобы скрыть факт автоматического управления браузером
        # и сделать автоматизированный браузер менее заметным, обходя некоторые защиты сайтов против ботов

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # Исключает определённые переключатели командной строки, в частности "enable-automation". Этот переключатель
        # обычно показывает на браузере надпись "Chrome is being controlled by automated test software"
        # (вкладка уведомляет, что браузер управляется скриптом). Исключение этой опции позволяет убрать это уведомление

        chrome_options.add_experimental_option("useAutomationExtension", False)
        # Отключает использование расширения автоматизации Chrome, которое по умолчанию используется Selenium,
        # чтобы помочь в управлении браузером. Отключение этого расширения помогает снизить вероятность того, что
        # веб-сайты обнаружат автоматизированный браузер

        chrome_options.add_argument("--disable-extensions")
        #  Этот аргумент отключает загрузку и работу всех расширений в браузере. Расширения — это
        #  дополнительные функции и инструменты, которые пользователь может установить в Chrome для улучшения или
        #  изменения функционала браузера. При автоматизации они могут мешать, влиять на стабильность или вызывать
        #  ранние обнаружения автоматизированного инструмента. Отключение расширений делает среду "чистой", без
        #  посторонних вмешательств

        chrome_options.add_argument("--disable-plugins")
        # Отключает все плагины, которые браузер бы загрузил. Плагины — это отдельные программы, которые работают
        # внутри браузера


        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--window-size=1920,1080")

        try:
            driver = webdriver.Chrome(options=chrome_options)

            stealth(
                driver,
                languages=["ru-RU", "ru"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True
            )
            # функция stealth подменяет параметры браузера и некоторые особенности его поведения, чтобы сделать
            # автоматизацию с помощью Selenium ближе к поведению реального пользователя и скрыть стандартные
            # признаки автоматизированного браузера

            driver.implicitly_wait(20)
            driver.set_page_load_timeout(60)
            #  Если за это время загрузка не завершится, будет выброшено исключение TimeoutException.
            # Это полезно для контроля времени ожидания и предотвращения длительных "зависаний" при медленной
            # загрузке страниц или проблемах с сетью

            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            # Это приём для маскировки факта автоматизации браузера и обхода механизмов защиты сайтов от ботов,
            # которые проверяют navigator.webdriver на наличие автоматизации

            self.driver = driver
            self.wait = WebDriverWait(driver, 20)

            logger.info("Chrome драйвер создан успешно")
            return driver

        except WebDriverException as e:
            logger.error(f"Ошибка создания Chrome драйвера: {e}")
            raise
            # Это ключевое слово повторно выбрасывает пойманное исключение дальше, то есть позволяет обработать
            # ошибку на более высоком уровне в программе

    def create_driver_with_logging(self) -> webdriver.Chrome:
        chrome_options = Options()

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option("perfLoggingPrefs", {'enableNetwork': True, 'enablePage': False})
        #



