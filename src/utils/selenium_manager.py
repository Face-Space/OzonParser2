import json
import logging
import time

from selenium import webdriver
from typing import Optional

from selenium.common.exceptions import WebDriverException, TimeoutException
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
        # Параметры внутри словаря сообщают ChromeDriver, какие именно события производительности логировать:
        # 'enableNetwork': True — включить сбор сетевых событий (например, запросы и ответы HTTP).
        # 'enablePage': False — отключить события, связанные с загрузкой страницы и изменениями DOM.
        chrome_options.add_experimental_option('loggingPrefs', {'performance': 'ALL'})
        # 'performance': 'ALL' означает, что в логах производительности должны сохраняться все доступные события.
        # Это гарантирует, что при вызове driver.get_log('performance') мы получим полный лог сетевых событий,
        # который был включен первой настройкой

        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")

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

            driver.implicitly_wait(20)
            driver.set_page_load_timeout(60)

            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.driver = driver
            self.wait = WebDriverWait(driver, 20)

            logger.info("Chrome драйвер с логированием создан успешно")
            return driver

        except WebDriverException as e:
            logger.error(f"Ошибка создания Chrome драйвера с логированием: {e}")
            raise


    def navigate_to_url(self, url: str):
        if not self.driver:
            logger.error("Драйвер не инициализирован")
            return False

        try:
            logger.debug(f"Переход по URL: {url}")
            self.driver.get(url)
            self._wait_for_antibot_bypass()

            return True

        except TimeoutException:
            logger.error(f"Таймаут при загрузке: {url}")
            return False

        except WebDriverException as e:
            logger.error(f"Ошибка WebDriver: {e}")
            return False


    def wait_for_json_response(self, timeout: int = 90) -> Optional[str]:
        if not self.driver:
            return None

        try:
            logger.debug("Ожидание JSON ответа...")
            start_time = time.time()

            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
                # Ожидает до 30 секунд, пока значение document.readyState в браузере не станет "complete"
            )

            while time.time() - start_time < timeout:
                try:
                    page_source = self.driver.page_source
                    json_content = self._extract_json_from_html(page_source)

                    if json_content:
                        try:
                            data = json.loads(json_content)
                            # loads предназначена для преобразования (десериализации) строки в формате JSON
                            # в соответствующий объект Python

                            if "widgetStates" in data:
                                logger.debug("JSON ответ с widgetStates найден")
                                return json_content

                        except json.JSONDecodeError:
                            pass

                    time.sleep(2.5)  # Увеличенное время ожидания между проверками

                except Exception as e:
                    logger.debug(f"Ошибка проверки содержимого страницы: {e}")
                    time.sleep(2.5)  # Увеличенное время ожидания при ошибке
                    continue

            logger.warning(f"Таймаут ожидания JSON ответа после {timeout} секунд")
            return self._extract_json_from_html(self.driver.page_source)

        except Exception as e:
            logger.error(f"Ошибка ожидания JSON ответа: {e}")
            return None


    def _extract_json_from_html(self, html_content: str) -> Optional[str]:
        try:
            import re

            pre_pattern = r'<pre[^>]*>(.*?)</pre>'
            # этот шаблон ищет содержимое между тегами <pre> и </pre>, включая любые атрибуты в открывающем теге

            pre_match = re.search(pre_pattern, html_content, re.DOTALL | re.IGNORECASE)
            # флаг, который говорит, что для символа . (любой символ) учитываются ВСЕ символы, в том числе
            # и перенос строки \n. Без флага DOTALL символ . не захватывает переносы строк
            # re.IGNORECASE — флаг, который делает поиск регистр-независимым.
            # Это значит, что <pre>, <PRE>, <Pre> и т.п. будут распознаны одинаково

            if pre_match:
                json_content = pre_match.group(1).strip()
                # метод group возвращает часть текста, которая совпала с группой в регулярном выражении.
                # Здесь group(1) означает: взять текст, который совпал с первой захватывающей группой
                # (то есть первой парой круглых скобок) в вашем регулярном выражении.
                logger.debug("JSON найден в <pre> теге")
                return json_content

            first_brace = html_content.find('{')
            last_brace = html_content.rfind('}')
            # rfind метод строк, который ищет последнее вхождение подстроки в строку и возвращает индекс этого вхождения
            #  Если подстрока не найдена, возвращается −1

            if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
                json_content = html_content[first_brace:last_brace + 1]
                # Вырезается подстрока из html_content, начиная с позиции first_brace и до last_brace + 1
                # (в срезах Python конечный индекс не включается, поэтому добавляем +1, чтобы захватить скобку })
                logger.debug("JSON найден по поиску скобок")
                return json_content

            return None

        except Exception as e:
            logger.error(f"Ошибка извлечения JSON из HTML: {e}")
            return None


    def _wait_for_antibot_bypass(self, max_wait_time: int = 240):   # ⬅️ 120 → 240
        start_time = time.time()
        reload_attempts = 0
        max_reload_attempts = 3

        while time.time() - start_time < max_wait_time:
            try:
                if self._is_blocked():
                    if reload_attempts < max_reload_attempts:
                        logger.info(
                            f"Обнаружена блокировка, перезагрузка страницы"
                            f"(попытка {reload_attempts + 1}/{max_reload_attempts})"
                        )
                        self.driver.refresh()
                        reload_attempts += 1
                        time.sleep(15)
                        continue
                    else:
                        logger.warning("Превышено количество попыток, возвращаем новый драйвер")
                        raise Exception("Access blocked after retries")
                else:
                    logger.info("Антибот защита пройдена")
                    return

            except Exception as e:
                if "Access blocked" in str(e):
                    raise
                time.sleep(15)
                continue

        logger.warning(f"Антибот защита не пройдена за {max_wait_time} секунд")
        raise Exception("AntibotTimeout")


    def _is_blocked(self) -> bool:
        if not self.driver:
            return True

        try:
            blocked_indicators = [
                "cloudflare", "checking your browser", "enable javascript",
                "access denied", "blocked", "ddos-guard", "проверка браузера",
                "доступ ограничен", "access restricted"
            ]

            page_source = self.driver.page_source.lower()

            for indicator in blocked_indicators:
                if indicator in page_source:
                    return True
            return False

        except Exception:
            return True


    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.debug("Драйвер закрыт успешно")
                
            except Exception as e:
                logger.error(f"Ошибка закрытия драйвера: {e}")

            finally:
                self.driver = None
                self.wait = None
