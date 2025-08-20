import logging
from typing import List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SellerInfo:
    seller_id: str
    company_name: str = ""
    inn: str = ""
    orders_count: str = ""
    reviews_count: str = ""
    working_time: str = ""
    average_rating: str = ""
    success: bool = False
    error: str = ""


class OzonSellerParser:
    def __init__(self, max_workers: int = 5, user_id: str = None):
        self.max_workers = max_workers
        self.user_id = user_id
        logger.info(f"Парсер продавцов инициализирован с макс {max_workers} воркерами для пользователя {user_id}")

    def parse_sellers(self, seller_ids: List[str]) -> List[SellerInfo]:
        unique_seller_ids = list(set(seller_ids))

        if not unique_seller_ids:
            logger.error(f"Не найдено ID продавцов для парсинга")
            return []


