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
import shutil
import difflib

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KhlResultsParser:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.base_url = "https://fon.bet/results/hockey/13283"  # Прямая ссылка на КХЛ
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

    def navigate_to_date(self, target_date):
        """Переход на страницу с результатами для конкретной даты"""
        try:
            # Форматируем дату для URL
            date_str = target_date.strftime("%Y-%m-%d")
            url = f"{self.base_url}?date={date_str}"

            logger.info(f"Переход на страницу результатов: {url}")
            self.driver.get(url)

            # Ожидание загрузки
            self.wait_for_page_load()
            time.sleep(3)

            # Проверяем, что мы на правильной странице
            current_url = self.driver.current_url
            if date_str in current_url:
                logger.info(f"Успешно перешли на страницу результатов КХЛ за {date_str}")
                return True
            else:
                logger.warning(f"Возможно не удалось перейти на нужную дату. Текущий URL: {current_url}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу результатов: {e}")
            return False

    def accept_cookies_if_present(self):
        """Принятие cookies, если появилось окно"""
        try:
            time.sleep(2)

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

    def should_process_event(self, event_time_str):
        """Определяем, нужно ли обрабатывать событие"""
        try:
            # Парсим время события
            event_time = datetime.strptime(event_time_str, "%d.%m.%Y %H:%M")
            current_time = datetime.now()

            # Если событие в будущем - пропускаем
            if event_time > current_time:
                logger.info(f"Событие {event_time_str} в будущем - пропускаем")
                return False

            # Проверяем, прошло ли больше 3 дней с момента события
            time_since_start = current_time - event_time
            if time_since_start > timedelta(days=3):
                logger.info(f"Событие {event_time_str} прошло более 3 дней назад - пропускаем")
                return False

            # Проверяем, прошло ли достаточно времени с момента начала матча
            # (матчи обычно длятся 2-3 часа, добавляем запас)
            if time_since_start < timedelta(hours=2):
                logger.info(f"Событие {event_time_str} началось недавно - возможно еще не завершено")
                return False

            logger.info(f"Событие {event_time_str} подходит для обработки")
            return True

        except Exception as e:
            logger.error(f"Ошибка при проверке события {event_time_str}: {e}")
            return False

    def normalize_team_name(self, name):
        """Нормализация названия команды для сравнения"""
        # Заменяем латинские буквы на кириллические
        replacements = {
            'c': 'с',  # латинская c -> кириллическая с
            'a': 'а',  # латинская a -> кириллическая а
            'e': 'е',  # латинская e -> кириллическая е
            'o': 'о',  # латинская o -> кириллическая о
            'p': 'р',  # латинская p -> кириллическая р
            'x': 'х',  # латинская x -> кириллическая х
            'y': 'у',  # латинская y -> кириллическая у,
            'k': 'к',  # латинская k -> кириллическая к
            'b': 'б',  # латинская b -> кириллическая б
        }

        normalized = name.lower()
        for lat, cyr in replacements.items():
            normalized = normalized.replace(lat, cyr)

        # Убираем лишние пробелы и приводим к нижнему регистру
        return ' '.join(normalized.split())

    def find_best_match(self, event_name, available_names):
        """Поиск наилучшего совпадения среди доступных названий"""
        normalized_event = self.normalize_team_name(event_name)

        best_match = None
        best_ratio = 0

        for available_name in available_names:
            normalized_available = self.normalize_team_name(available_name)

            # Простое сравнение строк
            if normalized_event == normalized_available:
                return available_name

            # Сравнение с использованием difflib для частичных совпадений
            ratio = difflib.SequenceMatcher(None, normalized_event, normalized_available).ratio()

            if ratio > best_ratio and ratio > 0.7:  # Понижен порог до 70% для лучшего сопоставления
                best_ratio = ratio
                best_match = available_name

        return best_match

    def parse_all_match_results_on_page(self):
        """Парсинг ВСЕХ результатов матчей на текущей странице"""
        try:
            # Даем время для полной загрузки
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Ищем все события на странице
            event_elements = soup.find_all('div', class_='results-event--Me6XJ')
            logger.info(f"Найдено событий на странице: {len(event_elements)}")

            results = {}
            available_names = []  # Сохраняем все найденные названия для отладки

            for event_element in event_elements:
                try:
                    # Парсим названия команд - улучшенный поиск
                    team_name_selectors = [
                        'div.results-event-team__name--lRkNU div.overflowed-text--JHSWr',
                        'div.results-event-team__caption--Ra_Se',
                        'div[class*="event-team__name"]'
                    ]

                    team_names = []
                    for selector in team_name_selectors:
                        name_elements = event_element.select(selector)
                        if name_elements and len(name_elements) >= 2:
                            team_names = [elem.get_text(strip=True) for elem in name_elements[:2]]
                            break

                    if len(team_names) < 2:
                        continue

                    team1_name = team_names[0]
                    team2_name = team_names[1]

                    # Создаем ключ для поиска в нашем CSV
                    event_key_1 = f"{team1_name} — {team2_name}"
                    event_key_2 = f"{team2_name} — {team1_name}"

                    available_names.append(event_key_1)
                    available_names.append(event_key_2)

                    logger.info(f"Найдены команды: {team1_name} vs {team2_name}")

                    # ПРОВЕРКА НА ОВЕРТАЙМ И БУЛЛИТЫ
                    overtime_selector = 'div.results-scoreBlock--aHrej.results-scoreBoard__sum-subEvents--_LZ3a'
                    overtime_elements = event_element.select(overtime_selector)

                    is_overtime_or_shootout = False
                    winning_team = None

                    if overtime_elements:
                        for ot_element in overtime_elements:
                            ot_scores = ot_element.select('div.results-scoreBlock__score--XvlMM')
                            if len(ot_scores) >= 2:
                                ot_text_1 = ot_scores[0].get_text(strip=True)
                                ot_text_2 = ot_scores[1].get_text(strip=True)

                                # Проверяем наличие OT (овертайм) или Б (буллиты)
                                if ot_text_1 in ['OT', 'ОТ'] or ot_text_2 in ['OT', 'ОТ']:
                                    is_overtime_or_shootout = True
                                    logger.info(f"Матч закончился в овертайме: {event_key_1}")

                                    # Определяем победившую команду по овертайму
                                    if ot_text_1 and not ot_text_2:
                                        winning_team = team1_name
                                    elif ot_text_2 and not ot_text_1:
                                        winning_team = team2_name
                                    break

                                elif ot_text_1 in ['Б', 'B'] or ot_text_2 in ['Б', 'B']:
                                    is_overtime_or_shootout = True
                                    logger.info(f"Матч закончился в буллитах: {event_key_1}")

                                    # Определяем победившую команду по буллитам
                                    if ot_text_1 and not ot_text_2:
                                        winning_team = team1_name
                                    elif ot_text_2 and not ot_text_1:
                                        winning_team = team2_name
                                    break

                    # УЛУЧШЕННЫЙ ПАРСИНГ СЧЕТА
                    score_selectors = [
                        'div.results-scoreBlock__score--XvlMM._summary--Jt8Ej._bold--JaGTY',
                        'div[class*="scoreBlock__score"][class*="_summary"]',
                        'div.results-scoreBlock__score--XvlMM'
                    ]

                    final_scores = []
                    for selector in score_selectors:
                        score_elements = event_element.select(selector)
                        if score_elements and len(score_elements) >= 2:
                            # Берем последние два элемента (финальный счет)
                            final_scores = [elem.get_text(strip=True) for elem in score_elements[-2:]]
                            if all(score.isdigit() for score in final_scores):
                                break

                    if len(final_scores) >= 2 and all(score.isdigit() for score in final_scores):
                        score1 = final_scores[0]
                        score2 = final_scores[1]

                        if is_overtime_or_shootout:
                            # Для матчей с овертаймом/буллитами создаем специальный результат
                            result_type = "OT" if any(text in ['OT', 'ОТ'] for text in [ot_text_1, ot_text_2]) else "Б"
                            result = f"{score1}:{score2} {result_type}"

                            # Добавляем информацию о победителе
                            if winning_team:
                                result += f" ({winning_team})"
                        else:
                            result = f"{score1}:{score2}"

                        # Сохраняем оба варианта названия (прямой и обратный)
                        results[event_key_1] = result
                        results[event_key_2] = result
                        logger.info(f"Результат матча: {event_key_1} - {result}")
                    else:
                        # Альтернативный метод: поиск по структуре таблицы
                        score_blocks = event_element.select('div.results-scoreBlock--aHrej')
                        if score_blocks:
                            # Последний блок обычно содержит финальный счет
                            last_block = score_blocks[-1]
                            scores = last_block.select('div.results-scoreBlock__score--XvlMM')
                            if len(scores) >= 2:
                                score1 = scores[0].get_text(strip=True)
                                score2 = scores[1].get_text(strip=True)
                                if score1.isdigit() and score2.isdigit():
                                    if is_overtime_or_shootout:
                                        # Для матчей с овертаймом/буллитами создаем специальный результат
                                        result_type = "OT" if any(
                                            text in ['OT', 'ОТ'] for text in [ot_text_1, ot_text_2]) else "Б"
                                        result = f"{score1}:{score2} {result_type}"

                                        # Добавляем информацию о победителе
                                        if winning_team:
                                            result += f" ({winning_team})"
                                    else:
                                        result = f"{score1}:{score2}"

                                    results[event_key_1] = result
                                    results[event_key_2] = result
                                    logger.info(f"Результат матча (альтернативный метод): {event_key_1} - {result}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке элемента события: {e}")
                    continue

            logger.info(f"Всего найдено результатов на странице: {len(results)}")
            logger.info(f"Доступные названия событий: {available_names}")
            return results

        except Exception as e:
            logger.error(f"Ошибка при парсинге результатов на странице: {e}")
            return {}

    def is_already_processed(self, row):
        """Проверяем, обработана ли уже строка (есть ли WIN/LOSS в котировках)"""
        try:
            # Проверяем основные котировки на наличие WIN/LOSS
            odds_1 = str(row.get('odds_1', ''))
            odds_x = str(row.get('odds_x', ''))
            odds_2 = str(row.get('odds_2', ''))

            # Если в любой из основных котировок есть WIN или LOSS - строка уже обработана
            if any(marker in odds_1.upper() or marker in odds_x.upper() or marker in odds_2.upper()
                   for marker in ['WIN', 'LOSS']):
                return True

            # Также проверяем тоталы
            total_over = str(row.get('total_over', ''))
            total_under = str(row.get('total_under', ''))

            if any(marker in total_over.upper() or marker in total_under.upper()
                   for marker in ['WIN', 'LOSS']):
                return True

            return False

        except Exception as e:
            logger.error(f"Ошибка при проверке обработки строки: {e}")
            return False

    def has_match_result(self, row):
        """Проверяем, есть ли уже результат матча"""
        try:
            match_result = str(row.get('match_result', '')).strip()
            return bool(match_result and match_result != '')
        except Exception as e:
            logger.error(f"Ошибка при проверке результата матча: {e}")
            return False

    def update_odds_with_results(self, row, result):
        """Обновление котировок на основе результата"""
        try:
            # Проверяем, является ли результат матчем с овертаймом/буллитами
            is_overtime_or_shootout = 'OT' in result or 'Б' in result or 'ОТ' in result

            if is_overtime_or_shootout:
                # Для матчей с овертаймом/буллитами ставим WIN на ничью (X)
                row['odds_1'] = f"LOSS {row['odds_1']}"
                row['odds_x'] = f"WIN {row['odds_x']}"
                row['odds_2'] = f"LOSS {row['odds_2']}"

                # Извлекаем счет для тоталов (убираем OT/Б часть)
                score_part = result.split()[0]  # Берем только часть со счетом "3:2"
                score1, score2 = map(int, score_part.split(':'))

                # Обновляем event_name с информацией о победителе
                if '(' in result and ')' in result:
                    # Извлекаем имя победившей команды из скобок
                    winner_start = result.find('(') + 1
                    winner_end = result.find(')')
                    winning_team = result[winner_start:winner_end]

                    # Добавляем информацию о победителе в название события
                    if winning_team and winning_team not in row['event_name']:
                        row['event_name'] = f"{row['event_name']} ({winning_team})"
                        logger.info(f"Добавлен победитель в название события: {winning_team}")

            else:
                # Обычный матч (основное время)
                score1, score2 = map(int, result.split(':'))

                # Определяем исход матча
                if score1 > score2:
                    # Победа первой команды
                    row['odds_1'] = f"WIN {row['odds_1']}"
                    row['odds_x'] = f"LOSS {row['odds_x']}"
                    row['odds_2'] = f"LOSS {row['odds_2']}"
                elif score1 < score2:
                    # Победа второй команды
                    row['odds_1'] = f"LOSS {row['odds_1']}"
                    row['odds_x'] = f"LOSS {row['odds_x']}"
                    row['odds_2'] = f"WIN {row['odds_2']}"
                else:
                    # Ничья
                    row['odds_1'] = f"LOSS {row['odds_1']}"
                    row['odds_x'] = f"WIN {row['odds_x']}"
                    row['odds_2'] = f"LOSS {row['odds_2']}"

            # Обновляем тоталы (для обоих случаев)
            total_score = score1 + score2
            total_value = float(row['total_value']) if row['total_value'] and row['total_value'].replace('.',
                                                                                                         '').isdigit() else 5.5

            if total_score > total_value:
                row['total_over'] = f"WIN {row['total_over']}"
                row['total_under'] = f"LOSS {row['total_under']}"
            elif total_score < total_value:
                row['total_over'] = f"LOSS {row['total_over']}"
                row['total_under'] = f"WIN {row['total_under']}"
            else:
                # Если тотал равен - обе котировки WIN
                row['total_over'] = f"WIN {row['total_over']}"
                row['total_under'] = f"WIN {row['total_under']}"

            return row

        except Exception as e:
            logger.error(f"Ошибка при обновлении котировок: {e}")
            return row

    def safe_file_operation(self, filename, operation, *args):
        """Безопасная операция с файлом с несколькими попытками"""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                return operation(filename, *args)
            except PermissionError:
                if attempt < max_attempts - 1:
                    logger.warning(f"Файл {filename} заблокирован, попытка {attempt + 1} из {max_attempts}")
                    time.sleep(2)
                else:
                    logger.error(f"Файл {filename} все еще заблокирован после {max_attempts} попыток")
                    raise
            except Exception as e:
                logger.error(f"Ошибка при работе с файлом {filename}: {e}")
                raise

    def load_csv_data(self, filename):
        """Загрузка данных из CSV файла"""

        def read_file(fname):
            with open(fname, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames
                rows = list(reader)
                return fieldnames, rows

        return self.safe_file_operation(filename, read_file)

    def save_csv_data(self, filename, fieldnames, rows):
        """Сохранение данных в CSV файл"""

        def write_file(fname, fnames, rws):
            with open(fname, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fnames)
                writer.writeheader()
                writer.writerows(rws)

        return self.safe_file_operation(filename, write_file, fieldnames, rows)

    def merge_rows(self, existing_rows, new_rows):
        """Объединение существующих и новых строк с сохранением результатов"""
        merged_rows = []

        # Создаем словарь для быстрого поиска существующих строк
        existing_dict = {}
        for row in existing_rows:
            key = (row.get('event_name', ''), row.get('event_time', ''), row.get('parse_timestamp', ''))
            existing_dict[key] = row

        # Обрабатываем новые строки
        for new_row in new_rows:
            key = (new_row.get('event_name', ''), new_row.get('event_time', ''), new_row.get('parse_timestamp', ''))

            if key in existing_dict:
                # Если строка уже существует, проверяем есть ли результат
                existing_row = existing_dict[key]
                if self.has_match_result(existing_row) or self.is_already_processed(existing_row):
                    # Сохраняем существующую строку с результатом
                    merged_rows.append(existing_row)
                    logger.info(f"Сохранен существующий результат для: {existing_row['event_name']}")
                else:
                    # Используем новую строку (без результата)
                    merged_rows.append(new_row)
            else:
                # Новая строка, добавляем как есть
                merged_rows.append(new_row)

        return merged_rows

    def process_csv_file(self, input_filename='khl_odds.csv', output_filename='khl_results_final.csv'):
        """Основной метод обработки CSV файла с сохранением существующих результатов"""
        try:
            logger.info(f"Используем выходной файл: {output_filename}")

            # Загружаем данные из исходного файла
            try:
                fieldnames, input_rows = self.load_csv_data(input_filename)
                logger.info(f"Загружено {len(input_rows)} событий из {input_filename}")
            except FileNotFoundError:
                logger.error(f"Исходный файл {input_filename} не найден")
                return False

            # Проверяем, существует ли уже выходной файл
            if os.path.exists(output_filename):
                logger.info(f"Выходной файл {output_filename} уже существует, загружаем существующие данные")
                try:
                    existing_fieldnames, existing_rows = self.load_csv_data(output_filename)
                    logger.info(f"Загружено {len(existing_rows)} существующих записей из {output_filename}")

                    # Объединяем данные, сохраняя существующие результаты
                    all_rows = self.merge_rows(existing_rows, input_rows)
                    logger.info(f"После объединения: {len(all_rows)} записей")

                except Exception as e:
                    logger.warning(f"Не удалось загрузить существующий файл {output_filename}: {e}")
                    all_rows = input_rows
            else:
                logger.info(f"Выходной файл {output_filename} не существует, создаем новый")
                all_rows = input_rows

            # Добавляем колонку для результатов если ее нет
            if 'match_result' not in fieldnames:
                fieldnames.append('match_result')
                for row in all_rows:
                    if 'match_result' not in row:
                        row['match_result'] = ''
                logger.info("Добавлена колонка match_result")

            # Принимаем cookies на первой странице
            self.navigate_to_date(datetime.now().date())
            self.accept_cookies_if_present()

            # Группируем события по датам для оптимизации
            events_by_date = {}
            for i, row in enumerate(all_rows):
                # Пропускаем уже обработанные строки (с WIN/LOSS)
                if self.is_already_processed(row):
                    logger.info(f"Строка {i} уже обработана (есть WIN/LOSS) - пропускаем")
                    continue

                # Пропускаем если результат уже есть
                if self.has_match_result(row):
                    logger.info(f"Строка {i} уже имеет результат - пропускаем")
                    continue

                event_time = row['event_time']
                if not self.should_process_event(event_time):
                    logger.info(f"Событие {event_time} не подходит для обработки - пропускаем")
                    continue

                try:
                    event_date = datetime.strptime(event_time, "%d.%m.%Y %H:%M").date()
                    if event_date not in events_by_date:
                        events_by_date[event_date] = []
                    events_by_date[event_date].append((i, row))
                except Exception as e:
                    logger.error(f"Ошибка при обработке даты события {event_time}: {e}")
                    continue

            logger.info(
                f"Событий для обработки по датам: { {date: len(events) for date, events in events_by_date.items()} }")

            updated_count = 0
            skipped_count = 0

            # Обрабатываем события по датам
            for event_date, date_events in events_by_date.items():
                logger.info(f"Обработка даты: {event_date}, событий: {len(date_events)}")

                # Устанавливаем дату в календаре
                if self.navigate_to_date(event_date):
                    # Парсим ВСЕ результаты на этой дате
                    date_results = self.parse_all_match_results_on_page()

                    if not date_results:
                        logger.warning(f"Не найдено результатов для даты {event_date}")
                        continue

                    # Обновляем все события этой даты
                    for i, row in date_events:
                        event_name = row['event_name']

                        # Дополнительная проверка на случай если строка уже обработана
                        if self.is_already_processed(row) or self.has_match_result(row):
                            skipped_count += 1
                            logger.info(f"Строка {i} ({event_name}) уже обработана - пропускаем")
                            continue

                        # Ищем результат в распарсенных данных
                        result = None
                        if event_name in date_results:
                            result = date_results[event_name]
                            logger.info(f"Точное совпадение для: {event_name}")
                        else:
                            # Используем улучшенный поиск совпадений
                            best_match = self.find_best_match(event_name, date_results.keys())
                            if best_match:
                                result = date_results[best_match]
                                logger.info(f"Найдено совпадение для '{event_name}' -> '{best_match}'")

                        if result:
                            # Обновляем результат
                            all_rows[i]['match_result'] = result
                            # Обновляем котировки
                            all_rows[i] = self.update_odds_with_results(all_rows[i], result)
                            updated_count += 1
                            logger.info(f"Обновлено событие: {event_name} - {result}")
                        else:
                            logger.warning(f"Не удалось найти результат для: {event_name}")
                            logger.warning(f"Доступные результаты: {list(date_results.keys())}")

                    # Небольшая пауза между датами
                    time.sleep(2)

            # Сохраняем обновленные данные
            try:
                self.save_csv_data(output_filename, fieldnames, all_rows)
                logger.info(f"Данные успешно сохранены в {output_filename}")
                logger.info(
                    f"Обработка завершена. Обновлено: {updated_count}, Пропущено (уже обработаны): {skipped_count}")
                return True

            except Exception as e:
                logger.error(f"Ошибка при сохранении файла: {e}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при обработке CSV файла: {e}")
            return False

    def run(self):
        """Основной метод запуска парсера результатов"""
        try:
            logger.info("Запуск парсера результатов FonBet для КХЛ...")

            success = self.process_csv_file()

            if success:
                print("✅ Парсинг результатов завершен успешно!")
                print("📊 Данные сохранены в файл khl_results_final.csv")
            else:
                print("❌ Произошла ошибка при парсинге результатов")

        except Exception as e:
            logger.error(f"Ошибка при работе парсера результатов: {e}")
            print(f"❌ Критическая ошибка: {e}")

        finally:
            if self.driver:
                self.driver.quit()
                logger.info("Браузер закрыт")


def main():
    """Основная функция"""
    print("🚀 Запуск парсера результатов FonBet для Континентальной Хоккейной Лиги (КХЛ)")
    print("⏳ Инициализация...")

    parser = KhlResultsParser(headless=False)  # False - видимый режим для отладки
    parser.run()


if __name__ == "__main__":
    main()