import logging
import json
import time
import re
import html
from typing import List, Dict, Tuple
from dataclasses import dataclass

from ..utils.selenium_manager import SeleniumManager
from ..utils.resource_manager import resource_manager

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


class SellerWorker:
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.selenium_manager = SeleniumManager()
        self.driver = None
        logger.info(f"Воркер продавцов {worker_id} инициализирован")

    def initialize(self):
        try:
            self.driver = self.selenium_manager.create_driver()
            logger.info(f"Воркер продавцов {self.worker_id} готов к работе")
        except Exception as e:
            logger.error(f"Ошибка инициализации продавцов {self.worker_id}: {e}")
            raise

    def parse_sellers(self, seller_ids: List[str]) -> List[SellerInfo]:
        results = []

        for seller_id in seller_ids:
            try:
                result = self._parse_single_seller(seller_id)


    def _parse_single_seller(self, seller_id: str) -> SellerInfo:
        max_retries = 3

        for attempt in range(max_retries):
            try:
                api_url = f"https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=/modal/shop-in-shop-info?seller_id={seller_id}&__rr=1"

                if not self.selenium_manager.navigate_to_url(api_url):
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return SellerInfo(seller_id=seller_id, error="Не удалось загрузить страницу API")

                json_content = self.selenium_manager.wait_for_json_response(timeout=30)

                if not json_content:
                    if attempt < max_retries:
                        time.sleep(5)
                        continue
                    return SellerInfo(seller_id=seller_id, error="Не получен JSON ответ")

                seller_info = self._parse_json_response(seller_id, json_content)


    def _parse_json_response(self, seller_id: str, json_content: str) -> SellerInfo:
        try:
            data = json.loads(json_content)

            if 'widgetStates' not in data:
                return SellerInfo(seller_id=seller_id, error="Отсутствует widgetStates в ответе")

            widget_states = data['widgetStates']
            seller_info = SellerInfo(seller_id=seller_id)

            # 1. Выбираем лучший textBlock
            seller_info.company_name, seller_info.inn = self._pick_best_text_block(widget_states)


    def _pick_best_text_block(self, widget_states: Dict[str, str]) -> Tuple[str, str]:
        best_company, best_inn = "", ""
        best_score = ""

        # Сначала собираем все textBlock'и с их данными
        text_blocks = []
        for key, value in widget_states.items():
            if not key.startswith("textBlock-"):
                continue

            company, inn = self._extract_company_data(value)
            if company or inn:  # Только если есть хоть какие-то данные
                text_blocks.append({
                    'key': key,
                    'company': company,
                    'inn': inn,
                    'raw_data': value
                })

        # Принимаем улучшенную логику скоринга
        for block in text_blocks:
            company = block["company"]
            inn = block["inn"]

            score = self._calculate_text_block_score(company, inn, block['raw_data'])


    def _calculate_text_block_score(self, company: str, inn: str, raw_data: str) -> int:
        """Улучшенная система скоринга для определения правильного textBlock"""
        score = 0

        # Базовые очки за наличие данных
        if company:
            score += 10
        if inn:
            score += 15
            # ИНН более важен для идентификации

        # Штрафы за нежелательные фразы
        unwanted_phrases = [
            "О магазине", "Оригинальные товары", "Premium магазин",
            "Понятно", "Заказов", "Работает с Ozon", "Средняя оценка",
            "Количество отзывов", "Это крупный магазин"
        ]

        company_lower = company.lower() if company else ""
        for phrase in unwanted_phrases:
            if phrase.lower() in company_lower:
                score -= 20  # Большой штраф за служебные фразы

        # Бонусы за признаки названия компании
        if company:
            # Проверяем на организационно-правовые нормы
            legal_forms = ["ООО", "ИП", "АО", "ЗАО", "ПАО", "Ltd", "LLC", "Inc", "Co"]
            for form in legal_forms:
                if form in company:
                    score += 5

            # Бонус за кавычки (часто в названиях компаний)
            if '"' in company or '«' in company:
                score += 3

            # Бонус за разумную длину названия компании (не слишком короткое, не слишком длинное)
            if 5 <= len(company.strip()) <= 100:
                score += 2

        # Проверяем структуру данных - если есть несколько textAtoms, это может быть название + доп. инфо
        try:
            data = json.loads(raw_data)
            if "body" in data and isinstance(data["body"], list):
                text_atoms = [item for item in data["body"] if item.get("type") == "textAtom"]

                # Если есть 2 textAtom - это хороший признак (название + график работы)
                if len(text_atoms) == 2:
                    first_text = text_atoms[0].get("textAtom", {}).get("text", "")
                    second_text = text_atoms[1].get("textAtom", {}).get("text", "")

                    # Проверяем, что второй текст похож на график работы
                    work_schedule_keywords = ["график", "работает", "согласно", "ozon", "время"]
                    if any(keyword in second_text.lower() for keyword in work_schedule_keywords):
                        score += 8  # Хороший признак правильного блока

                    # Дополнительная проверка первого текста на название компании
                    if first_text and not any(phrase.lower() in first_text.lower() for phrase in unwanted_phrases):
                        score += 5

        except:
            pass  # Игнорируем ошибки парсинга JSON

        return score


    def _extract_company_data(self, text_block_data: str) -> Tuple[str, str]:
        try:
            data = json.loads(text_block_data)
            if "body" not in data or not isinstance(data["body"], list):
                # код проверяет, что в загруженных данных присутствует ключ "body", и что по этому ключу хранится список
                return "", ""


            text_atoms = []
            for item in data["body"]:
                if item.get("type") == "textAtom":
                    text_atoms.append(item["textAtom"]["text"])

            if not text_atoms:
                return "", ""

            # Если есть несколько textAtom, обрабатываем их отдельно
            if len(text_atoms) >= 2:
                # Первый textAtom обычно содержит название компании
                first_text = text_atoms[0].strip()

                # Обрабатываем <br> теги в первом textAtom
                company = self._extract_company_name_from_text(first_text)

                # Ищем ИНН во всех трёх textAtom
                inn = ""
                for text in text_atoms:
                    inn_match = re.search(r"\d{10,15}", text)
                    if inn_match:
                        inn = inn_match.group(0)
                        break

                return company, inn

            # Если только один textAtom, используем улучшенную логику
            raw = text_atoms[0].split()

            # Сначала пробуем извлечь название компании с учетом <br>
            company = self._extract_company_name_from_text(raw)

            # Ищем ИНН в оригинальном тексте
            inn_match = re.search(r'\d{10,15}', raw)
            inn = inn_match.group(0) if inn_match else ""

            return company, inn

        except Exception:
            return "", ""



    def _extract_company_name_from_text(self, text: str) -> str:
        """Извлекает название компании из текста, обрабатывая <br> теги"""
        if not text:
            return ""

        # Список возможных вариантов <br> тегов
        br_variants = ["<br>", "&lt;br&gt;", "<br/>", "&lt;br/&gt;", "<br />", "&lt;br /&gt;"]

        # Ищем первый <br> тег и берем текст до него
        for br_tag in br_variants:
            if br_tag in text:
                company = text.split(br_tag, 1)
                break
            else:
                # Если <br> тегов нет, проверяем на ИНН в конце строки
                inn_match = re.search(r"(\d{10,15})$", text)
                if inn_match:
                    company = text[:inn_match.start()].strip()
                    # Убираем возможные разделители
                    company = re.sub(r'[,\s]+$', '', company)
                else:
                    company = text.strip()

            # Очищаем название компании от лишних символов
            company = self._clean_company_name(company)

            return html.unescape(company)


    def _clean_company_name(self, company: str) -> str:
        """Очищает названия компании от лишних символов и дублирования"""
        if not company:
            return ""

        # Убираем лишние пробелы
        company = re.sub(r'\s+', ' ', company).strip()

        # Исправляем дублирование ООО (например "ООО ООО "РОБОТКОМП КОРП"" -> "ООО "РОБОТКОМП КОРП"")
        company = re.sub(r'^(ООО|ИП|АО|ЗАО|ПАО)\s+(ООО|ИП|АО|ЗАО|ПАО)\s+', r'\1', company)

        # Убираем возможные разделители в конце
        company = re.sub(r'[,\s]+$', '', company)

        return company





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

        # Получаем количество воркеров от менеджера ресурсов
        if self.user_id:
            allocated_workers = resource_manager.start_parsing_session(
                self.user_id, 'sellers', len(unique_seller_ids)
            )
        else:
            allocated_workers = self._calculate_optimal_workers(len(unique_seller_ids))

        logger.info(f"Начало парсинга {len(unique_seller_ids)} продавцов с {allocated_workers} воркерами "
                    f"для пользователя {self.user_id}")

        try:
            if allocated_workers == 1:
                return self._parse_single_worker(unique_seller_ids)
            else:
                return self._parse_multiple_workers(unique_seller_ids, allocated_workers)
        finally:
            # Завершаем сессию парсинга
            if self.user_id:
                resource_manager.finish_parsing_session(self.user_id)


    def _parse_single_worker(self, seller_ids: List[str]) -> List[SellerInfo]:
        worker = SellerWorker(1)
        try:
            worker.initialize()
            return worker.parse_sellers(seller_ids)
        finally:
            worker.close()


    def _calculate_optimal_workers(self, total_sellers: int) -> int:
        if total_sellers <= 10:
            return 1
        elif total_sellers <= 25:
            return 2
        elif total_sellers <= 50:
            return 3
        else:
            return min(5, self.max_workers) # Максимум 5 воркеров






