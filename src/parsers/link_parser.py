import logging
import re
from datetime import datetime
from typing import Tuple, Dict

from ..utils.selenium_manager import SeleniumManager

logger = logging.getLogger(__name__)


class OzonLinkParser:

    def __init__(self, category_url: str, max_products: int = 100, user_id: str = None):
        self.category_url = category_url
        self.max_products = max_products
        self.user_id = user_id
        self.selenium_manager = SeleniumManager()
        self.driver = None
        self.collected_links = {}

        self.category_name = self._extract_category_name(category_url)
        self.timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")
        self.output_folder = f"{self.category_name}_{self.timestamp}"

    def _extract_category_name(self, url: str) -> str:
        try:
            match = re.search(f'/category/([^/]+)-(\d+)/', url)
            # .search ищет в переменной url первое совпадение с заданным шаблоном
            if match:
                return match.group(1).replace('-','_')
            if '/search/' in url:
                return "search"
            return "unknown_category"

        except Exception:
            return "unknown_category"

    def start_parsing(self) -> Tuple[bool, Dict[str, str]]:
        try:
            # Регистрируем сессию парсинга ссылок
            if self.user_id:
                resource_manager.start_parsing_session(self.user_id, 'links', self.max_products)





