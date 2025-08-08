import logging

logger = logging.getLogger(__name__)


class OzonLinkParser:

    def __init__(self, category_url: str, max_products: int = 100, user_id: str = None):
        self.category_url = category_url
        self.max_products = max_products
        self.user_id = user_id
        self.selenium_manager = SeleniumManager()
        self.driver = None
        self.collected_links = {}



