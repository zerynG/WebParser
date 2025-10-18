import time
import csv
import logging
import os
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KhlFonBetParser:
    def __init__(self, headless=False):
        self.driver = None
        self.headless = headless
        self.setup_driver()

    def setup_driver(self):
        """Настройка Selenium WebDriver с автоматической установкой драйвера"""
        try:
            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')

            # Правильная инициализация драйвера
            service = webdriver.chrome.service.Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)

            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("WebDriver успешно настроен")

        except Exception as e:
            logger.error(f"Ошибка при настройке WebDriver: {e}")
            raise

    def wait_for_page_load(self, timeout=10):
        """Ожидание загрузки страницы"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            logger.info("Страница полностью загружена")
        except TimeoutException:
            logger.warning("Страница не загрузилась полностью за отведенное время")

    def navigate_to_khl(self):
        """Переход к разделу КХЛ"""
        try:
            url = "https://fon.bet/sports/hockey/tournament/776"
            logger.info(f"Переход на страницу: {url}")
            self.driver.get(url)

            # Ожидание загрузки
            self.wait_for_page_load()
            time.sleep(5)  # Дополнительное время для загрузки динамического контента

            # Проверяем, что мы на правильной странице
            page_title = self.driver.title
            page_source = self.driver.page_source
            logger.info(f"Заголовок страницы: {page_title}")

            if "КХЛ" in page_title or "хоккей" in page_source.lower() or "KHL" in page_source:
                logger.info("Успешно перешли на страницу КХЛ")
            else:
                logger.warning("Возможно, не удалось загрузить нужную страницу")
                # Сохраним страницу для отладки
                with open('debug_khl_page.html', 'w', encoding='utf-8') as f:
                    f.write(page_source)
                logger.info("Страница сохранена в debug_khl_page.html для отладки")

        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу: {e}")
            raise

    def accept_cookies_if_present(self):
        """Принятие cookies, если появилось окно"""
        try:
            # Даем время для появления cookies окна
            time.sleep(2)

            # Попробуем найти и закрыть cookies окно
            cookie_selectors = [
                'button[class*="cookie"]',
                'button[class*="accept"]',
                'div[class*="cookie"] button',
                '//button[contains(text(), "Принять")]',
                '//button[contains(text(), "Accept")]',
                '//button[contains(text(), "Согласен")]'
            ]

            for selector in cookie_selectors:
                try:
                    if selector.startswith('//'):
                        button = self.driver.find_element(By.XPATH, selector)
                    else:
                        button = self.driver.find_element(By.CSS_SELECTOR, selector)

                    if button.is_displayed():
                        button.click()
                        logger.info("Cookies приняты")
                        time.sleep(1)
                        break
                except NoSuchElementException:
                    continue

        except Exception as e:
            logger.debug(f"Окно cookies не найдено или не может быть закрыто: {e}")

    def clean_text(self, text):
        """Очистка текста от специальных символов"""
        if not text:
            return ""
        # Удаляем специальные символы пробелов
        return text.replace(' ', '').replace(' ', '').strip()

    def parse_event_time(self, time_text):
        """Преобразование времени события в формат dd.mm.yyyy HH:MM"""
        try:
            now = datetime.now()
            current_year = now.year

            if "Завтра" in time_text:
                # Завтра
                date = now + timedelta(days=1)
                # Извлекаем время
                time_part = time_text.split(" в ")[1]
                event_datetime = datetime.combine(date.date(), datetime.strptime(time_part, "%H:%M").time())
                return event_datetime.strftime("%d.%m.%Y %H:%M")

            elif any(month in time_text.lower() for month in [
                'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'
            ]):
                # Дата в формате "9 октября в 02:00"
                parts = time_text.split(" ")
                day = int(parts[0])
                time_part = parts[3]  # время после "в"

                # Определяем месяц
                month_text = parts[1].lower()
                month_mapping = {
                    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
                    'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
                }

                month = month_mapping.get(month_text)
                if month:
                    # Используем текущий год
                    event_datetime = datetime(current_year, month, day,
                                              datetime.strptime(time_part, "%H:%M").hour,
                                              datetime.strptime(time_part, "%H:%M").minute)
                    return event_datetime.strftime("%d.%m.%Y %H:%M")

            elif "Сегодня" in time_text:
                # Сегодня
                time_part = time_text.split(" в ")[1]
                event_datetime = datetime.combine(now.date(), datetime.strptime(time_part, "%H:%M").time())
                return event_datetime.strftime("%d.%m.%Y %H:%M")

            else:
                # Если формат неизвестен, возвращаем оригинальный текст
                return time_text

        except Exception as e:
            logger.warning(f"Не удалось распарсить время: {time_text}, ошибка: {e}")
            return time_text

    def parse_event_data(self, event_element):
        """Парсинг данных одного события КХЛ"""
        try:
            # Название события
            name_selectors = [
                'a[class*="sport-event__name"]',
                'div[class*="event-name"]',
                'span[class*="event-name"]'
            ]

            event_name = "Название не найдено"
            for selector in name_selectors:
                name_element = event_element.select_one(selector)
                if name_element and name_element.text.strip():
                    event_name = name_element.text.strip()
                    break

            # Время и дата
            time_selectors = [
                'span[class*="event-block-planned-time"]',
                'span[class*="time"]',
                'div[class*="time"]'
            ]

            event_time_raw = "Время не найдено"
            for selector in time_selectors:
                time_element = event_element.select_one(selector)
                if time_element and time_element.text.strip():
                    event_time_raw = time_element.text.strip()
                    break

            # ПРЕОБРАЗОВАНИЕ: конвертируем в формат dd.mm.yyyy HH:MM
            if event_time_raw != "Время не найдено":
                event_time = self.parse_event_time(event_time_raw)
            else:
                event_time = event_time_raw

            # ... остальной код без изменений ...

            # Все простые котировки (значения без параметров)
            value_spans = event_element.find_all('span', class_='value--OUKql')
            all_simple_values = [span.text.strip() for span in value_spans]

            # Основные котировки (1, X, 2) - первые три значения
            main_odds = all_simple_values[:3] if len(all_simple_values) >= 3 else ["", "", ""]

            # Двойные шансы (1X, 12, X2) - следующие три значения
            double_chance_odds = all_simple_values[3:6] if len(all_simple_values) >= 6 else ["", "", ""]

            # УЛУЧШЕННЫЙ ПАРСИНГ ФОР
            fora_1 = ""
            fora_2 = ""

            # Ищем все комплексные элементы (форы)
            complex_elements = event_element.find_all('div', class_='table-component-factor-value_complex')

            for i, complex_element in enumerate(complex_elements):
                # Ищем параметр и значение внутри комплексного элемента
                param_spans = complex_element.find_all('span', class_='param--qbIN_')
                value_spans = complex_element.find_all('span', class_='value--OUKql')

                if len(param_spans) >= 1 and len(value_spans) >= 1:
                    param = self.clean_text(param_spans[0].text)
                    value = value_spans[0].text.strip()

                    if i == 0:
                        fora_1 = f"{param} {value}"
                    elif i == 1:
                        fora_2 = f"{param} {value}"

            # УЛУЧШЕННЫЙ ПАРСИНГ ТОТАЛОВ
            total_value = ""
            total_over = ""
            total_under = ""

            # Ищем элемент с параметром тотала
            total_param_elements = event_element.find_all('div', class_='table-component-factor-value_param')

            for total_element in total_param_elements:
                param_spans = total_element.find_all('span', class_='param--qbIN_')
                if param_spans:
                    total_value = self.clean_text(param_spans[0].text)

                    # Находим индекс этого элемента среди всех factor-value элементов
                    all_factors = event_element.find_all('div', class_='factor-value--zrkpK')

                    for idx, factor in enumerate(all_factors):
                        if factor == total_element:
                            # Следующие два элемента должны быть Over и Under
                            if idx + 1 < len(all_factors):
                                over_span = all_factors[idx + 1].find('span', class_='value--OUKql')
                                if over_span:
                                    total_over = over_span.text.strip()

                            if idx + 2 < len(all_factors):
                                under_span = all_factors[idx + 2].find('span', class_='value--OUKql')
                                if under_span:
                                    total_under = under_span.text.strip()
                            break

            # АЛЬТЕРНАТИВНЫЙ МЕТОД: поиск по позиции после двойных шансов
            if not fora_1 and not fora_2 and len(all_simple_values) >= 9:
                # Позиции 6-7 могут быть форами, 8-10 - тоталы
                if len(all_simple_values) > 6:
                    fora_1 = all_simple_values[6] if all_simple_values[6] else ""
                if len(all_simple_values) > 7:
                    fora_2 = all_simple_values[7] if all_simple_values[7] else ""
                if len(all_simple_values) > 8:
                    total_value = "5.5"  # Стандартное значение для хоккея
                    total_over = all_simple_values[8] if all_simple_values[8] else ""
                if len(all_simple_values) > 9:
                    total_under = all_simple_values[9] if all_simple_values[9] else ""

            # Формат даты парсинга dd.mm.yyyy HH:MM:SS
            parse_timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            return {
                'parse_timestamp': parse_timestamp,
                'event_name': event_name,
                'event_time': event_time,  # Теперь в формате dd.mm.yyyy HH:MM
                'odds_1': main_odds[0],
                'odds_x': main_odds[1],
                'odds_2': main_odds[2],
                'odds_1x': double_chance_odds[0] if len(double_chance_odds) > 0 else "",
                'odds_12': double_chance_odds[1] if len(double_chance_odds) > 1 else "",
                'odds_x2': double_chance_odds[2] if len(double_chance_odds) > 2 else "",
                'fora_1': fora_1,
                'fora_2': fora_2,
                'total_value': total_value,
                'total_over': total_over,
                'total_under': total_under
            }

        except Exception as e:
            logger.error(f"Ошибка при парсинге события: {e}")
            return None

    def parse_all_events(self):
        """Парсинг всех событий КХЛ"""
        try:
            # Принимаем cookies перед парсингом
            self.accept_cookies_if_present()

            # Даем время на обновление страницы
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Ищем события по различным возможным классам
            event_selectors = [
                '[class*="sport-base-event"]',
                '[class*="sport-event"]',
                '[class*="event-block"]',
                '.sport-base-event--W4qkO'
            ]

            events_data = []

            for selector in event_selectors:
                event_blocks = soup.select(selector)
                if event_blocks:
                    logger.info(f"Найдено {len(event_blocks)} элементов с селектором {selector}")
                    for event_block in event_blocks:
                        event_data = self.parse_event_data(event_block)
                        if event_data and event_data['event_name'] != "Название не найдено":
                            # Проверяем, что это действительно хоккейное событие КХЛ
                            if any(team in event_data['event_name'] for team in [
                                'Лада', 'Сочи', 'Ак Барс', 'Барыс', 'Торпедо', 'Металлург',
                                'Нефтехимик', 'Амур', 'Спартак', 'Дрэгонс', 'Автомобилист',
                                'СКА', 'Динамо Москва', 'Салават Юлаев', 'Трактор', 'Северсталь',
                                'Динамо Минск', 'Локомотив', 'ЦСКА', 'ХК'
                            ]):
                                events_data.append(event_data)
                    if events_data:
                        break

            # Убираем дубликаты по улучшенному ключу
            unique_events = []
            seen_keys = set()
            for event in events_data:
                # Ключ: только название + время (без котировок)
                event_key = f"{event['event_name']}|{event['event_time']}"
                if event_key not in seen_keys:
                    seen_keys.add(event_key)
                    unique_events.append(event)

            logger.info(f"Уникальных хоккейных событий КХЛ найдено: {len(unique_events)}")
            return unique_events

        except Exception as e:
            logger.error(f"Ошибка при парсинге событий: {e}")
            return []

    def load_existing_data(self, filename='khl_odds.csv'):
        """Загрузка существующих данных из CSV файла"""
        existing_data = []
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        existing_data.append(row)
                logger.info(f"Загружено {len(existing_data)} существующих событий из {filename}")
            except Exception as e:
                logger.error(f"Ошибка при чтении существующего файла: {e}")
        else:
            logger.info(f"Файл {filename} не существует, будет создан новый")

        return existing_data

    def get_existing_event_keys(self, existing_data):
        """Получение ключей существующих событий для проверки дубликатов"""
        event_keys = set()
        for event in existing_data:
            # Ключ: только название + время (без котировок)
            key = f"{event['event_name']}|{event['event_time']}"
            event_keys.add(key)
        return event_keys

    def save_to_csv(self, events_data, filename='khl_odds.csv'):
        """Сохранение данных в CSV файл с проверкой дубликатов"""
        if not events_data:
            logger.warning("Нет новых данных для сохранения")
            return 0, 0

        # Загружаем существующие данные
        existing_data = self.load_existing_data(filename)
        existing_event_keys = self.get_existing_event_keys(existing_data)

        # Определяем новые события
        new_events = []
        for event in events_data:
            # Ключ: только название + время (без котировок)
            event_key = f"{event['event_name']}|{event['event_time']}"
            if event_key not in existing_event_keys:
                new_events.append(event)

        if not new_events:
            logger.info("Новых событий для добавления не найдено")
            return len(existing_data), 0

        # Объединяем старые и новые данные
        all_events = existing_data + new_events

        # Обновляем fieldnames для КХЛ
        fieldnames = [
            'parse_timestamp', 'event_name', 'event_time',
            'odds_1', 'odds_x', 'odds_2',
            'odds_1x', 'odds_12', 'odds_x2',
            'fora_1', 'fora_2',
            'total_value', 'total_over', 'total_under'
        ]

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for event in all_events:
                    # Убедимся, что у всех событий есть parse_timestamp
                    if 'parse_timestamp' not in event:
                        event['parse_timestamp'] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                    writer.writerow(event)

            logger.info(f"Данные обновлены в файле: {filename}")
            logger.info(f"Всего событий: {len(all_events)} (добавлено новых: {len(new_events)})")

            return len(all_events), len(new_events)

        except Exception as e:
            logger.error(f"Ошибка при сохранении в CSV: {e}")
            return 0, 0

    def run(self):
        """Основной метод запуска парсера"""
        try:
            logger.info("Запуск парсера FonBet для КХЛ...")
            self.navigate_to_khl()

            logger.info("Начало парсинга данных...")
            events_data = self.parse_all_events()

            if events_data:
                total_events, new_events = self.save_to_csv(events_data)

                if new_events > 0:
                    logger.info("Парсинг завершен успешно!")
                    print(f"\n✅ Успешно! Добавлено {new_events} новых событий")
                    print(f"📊 Всего в базе: {total_events} событий")

                    # Вывод первых 3 новых событий для проверки
                    print("\n" + "=" * 60)
                    print("ПЕРВЫЕ 3 НОВЫХ СОБЫТИЯ КХЛ:")
                    print("=" * 60)

                    # Находим новые события для отображения
                    existing_data = self.load_existing_data()
                    existing_keys = self.get_existing_event_keys(existing_data)
                    new_events_to_show = []

                    for event in events_data:
                        event_key = f"{event['event_name']}|{event['event_time']}"
                        if event_key not in existing_keys:
                            new_events_to_show.append(event)
                        if len(new_events_to_show) >= 3:
                            break

                    for i, event in enumerate(new_events_to_show, 1):
                        print(f"\n🏒 Событие {i}: {event['event_name']}")
                        print(f"   ⏰ Время: {event['event_time']}")  # Теперь в формате dd.mm.yyyy HH:MM
                        print(f"   📊 Основные котировки:")
                        print(f"       1: {event['odds_1']} | X: {event['odds_x']} | 2: {event['odds_2']}")
                        print(f"   🔄 Двойные шансы:")
                        print(f"       1X: {event['odds_1x']} | 12: {event['odds_12']} | X2: {event['odds_x2']}")
                        print(f"   🎯 Форы:")
                        print(f"       Фора 1: {event['fora_1']}")
                        print(f"       Фора 2: {event['fora_2']}")
                        print(f"   📈 Тотал {event['total_value']}:")
                        print(f"       Over: {event['total_over']} | Under: {event['total_under']}")
                        print(f"   🕒 Время парсинга: {event['parse_timestamp']}")
                        print("-" * 40)

                    # Дополнительная отладочная информация
                    print(f"\n🔍 Отладочная информация:")
                    print(f"   Всего найдено событий: {len(events_data)}")
                    print(f"   Уникальных событий: {len(new_events_to_show)}")

                else:
                    print("\nℹ️  Новых событий не найдено, база данных актуальна")
                    print(f"📊 Всего в базе: {total_events} событий")
            else:
                logger.warning("Не удалось найти события КХЛ")
                print("❌ Не найдено событий. Проверьте:")
                print("   - Доступность сайта https://fon.bet")
                print("   - Наличие текущих матчей КХЛ")
                print("   - Файл debug_khl_page.html для анализа структуры страницы")

        except Exception as e:
            logger.error(f"Ошибка при работе парсера: {e}")
            print(f"❌ Критическая ошибка: {e}")

        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Браузер закрыт")


def main():
    """Основная функция"""
    print("🚀 Запуск парсера FonBet для Континентальной Хоккейной Лиги (КХЛ)")
    print("⏳ Инициализация...")

    parser = KhlFonBetParser(headless=False)  # False - видим браузер, True - скрытый режим
    parser.run()


if __name__ == "__main__":
    main()