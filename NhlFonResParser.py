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
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
from webdriver_manager.chrome import ChromeDriverManager
import shutil
import difflib

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NhlResultsParser:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.base_url = "https://fon.bet/results/hockey/11781"  # Прямая ссылка на НХЛ
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
                logger.info(f"Успешно перешли на страницу результатов НХЛ за {date_str}")
                return True
            else:
                logger.warning(f"Возможно не удалось перейти на нужную дату. Текущий URL: {current_url}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при переходе на страницу результатов: {e}")
            return False

    def search_event_by_name(self, event_name):
        """Поиск события по названию через строку поиска"""
        try:
            logger.info(f"Поиск события через строку поиска: {event_name}")

            # Находим поле поиска
            search_input = self.driver.find_element(By.CSS_SELECTOR, 'input.search-panel__input--xW3P5')

            # Очищаем поле поиска
            search_input.clear()
            time.sleep(1)

            # Вводим название события
            search_input.send_keys(event_name)
            time.sleep(2)  # Ждем обновления результатов

            # Ждем появления результатов поиска
            time.sleep(3)

            # Парсим результаты поиска
            search_results = self.parse_all_match_results_on_page()

            # Очищаем поле поиска для следующего поиска
            search_input.clear()
            time.sleep(1)

            logger.info(f"Найдено результатов в поиске: {len(search_results)}")
            return search_results

        except Exception as e:
            logger.error(f"Ошибка при поиске события '{event_name}': {e}")
            return {}

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

            if ratio > best_ratio and ratio > 0.7:  # Понизил порог до 70% для лучшего сопоставления
                best_ratio = ratio
                best_match = available_name

        return best_match

    def check_overtime_indicator(self, event_element):
        """Проверка наличия индикатора овертайма/буллитов"""
        try:
            # Ищем блок с овертаймом по классам из HTML шаблона
            overtime_blocks = event_element.select(
                'div.results-scoreBlock--aHrej.results-scoreBoard__sum-subEvents--_LZ3a')

            for block in overtime_blocks:
                # Ищем элементы с текстом OT (овертайм) или Б (буллиты)
                ot_elements = block.select('div.results-scoreBlock__score--XvlMM')
                for element in ot_elements:
                    element_text = element.get_text(strip=True)
                    if element_text in ['OT', 'ОТ', 'Б']:
                        logger.info(f"Найден индикатор овертайма/буллитов: {element_text}")
                        return True

            return False
        except Exception as e:
            logger.debug(f"Ошибка при проверке индикатора овертайма: {e}")
            return False

    def get_overtime_result(self, event_element):
        """Получение результата матча с овертаймом/буллитами"""
        try:
            # Ищем названия команд
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
                return None, None

            # Ищем финальный счет
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
                score1 = int(final_scores[0])
                score2 = int(final_scores[1])

                # Определяем победителя и корректируем счет
                if score1 > score2:
                    # Первая команда победила, вычитаем 1 гол у победителя
                    adjusted_score1 = score1 - 1
                    result = f"{adjusted_score1}:{score2}"
                    winner = team_names[0]
                elif score2 > score1:
                    # Вторая команда победила, вычитаем 1 гол у победителя
                    adjusted_score2 = score2 - 1
                    result = f"{score1}:{adjusted_score2}"
                    winner = team_names[1]
                else:
                    return None, None

                return result, winner

            return None, None

        except Exception as e:
            logger.error(f"Ошибка при определении результата в овертайме: {e}")
            return None, None

    def parse_all_match_results_on_page(self):
        """Парсинг ВСЕХ результатов матчей на текущей странице"""
        try:
            # Даем время для полной загрузки (прокрутка убрана)
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

                    # Проверяем наличие овертайма/буллитов ПЕРВЫМ делом
                    is_overtime = self.check_overtime_indicator(event_element)

                    if is_overtime:
                        # Матч закончился в овертайме/буллитах
                        result, winner = self.get_overtime_result(event_element)
                        if result and winner:
                            # Добавляем информацию о победителе в скобках
                            event_key_1_with_winner = f"{team1_name} — {team2_name} ({winner})"
                            event_key_2_with_winner = f"{team2_name} — {team1_name} ({winner})"

                            # Сохраняем оба варианта с информацией о победителе
                            results[event_key_1_with_winner] = result
                            results[event_key_2_with_winner] = result
                            logger.info(f"Матч с овертаймом: {event_key_1}, результат: {result}, победитель: {winner}")
                        else:
                            logger.warning(f"Не удалось определить результат овертайма для: {event_key_1}")
                        continue

                    # Обычные матчи (без овертайма)
                    # Ищем финальный счет - РАСШИРЕННЫЙ ПОИСК
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

                    # Если не нашли через селекторы, пробуем альтернативные методы
                    if not final_scores or len(final_scores) < 2:
                        # Метод 1: Поиск по всем элементам счета
                        all_score_elements = event_element.select('div.results-scoreBlock__score--XvlMM')
                        if len(all_score_elements) >= 2:
                            # Берем последние два цифровых значения
                            digit_scores = []
                            for elem in reversed(all_score_elements):
                                text = elem.get_text(strip=True)
                                if text.isdigit():
                                    digit_scores.insert(0, text)
                                    if len(digit_scores) == 2:
                                        break
                            if len(digit_scores) == 2:
                                final_scores = digit_scores

                    # Метод 2: Поиск по структуре блоков
                    if not final_scores or len(final_scores) < 2:
                        score_blocks = event_element.select('div.results-scoreBlock--aHrej')
                        if score_blocks:
                            # Последний блок обычно содержит финальный счет
                            last_block = score_blocks[-1]
                            scores = last_block.select('div.results-scoreBlock__score--XvlMM')
                            if len(scores) >= 2:
                                score1 = scores[0].get_text(strip=True)
                                score2 = scores[1].get_text(strip=True)
                                if score1.isdigit() and score2.isdigit():
                                    final_scores = [score1, score2]

                    # Метод 3: Поиск по элементам с классом _summary
                    if not final_scores or len(final_scores) < 2:
                        summary_scores = event_element.select('div.results-scoreBlock__score--XvlMM._summary--Jt8Ej')
                        if len(summary_scores) >= 2:
                            score1 = summary_scores[-2].get_text(strip=True)
                            score2 = summary_scores[-1].get_text(strip=True)
                            if score1.isdigit() and score2.isdigit():
                                final_scores = [score1, score2]

                    if len(final_scores) >= 2 and all(score.isdigit() for score in final_scores):
                        score1 = final_scores[0]
                        score2 = final_scores[1]
                        result = f"{score1}:{score2}"

                        # Сохраняем оба варианта названия (прямой и обратный)
                        results[event_key_1] = result
                        results[event_key_2] = result
                        logger.info(f"Результат обычного матча: {event_key_1} - {result}")
                    else:
                        # Если счет не найден, логируем для отладки
                        all_score_texts = [elem.get_text(strip=True) for elem in
                                           event_element.select('div.results-scoreBlock__score--XvlMM')]
                        logger.warning(f"Не удалось найти счет для: {event_key_1}")
                        logger.warning(f"Все найденные элементы счета: {all_score_texts}")

                except Exception as e:
                    logger.error(f"Ошибка при обработке элемента события: {e}")
                    continue

            logger.info(f"Всего найдено результатов на странице: {len(results)}")
            logger.info(f"Доступные названия событий: {available_names}")

            # Дополнительная отладка: выводим все найденные результаты
            for key, value in results.items():
                logger.info(f"Найден результат: {key} -> {value}")

            return results

        except Exception as e:
            logger.error(f"Ошибка при парсинге результатов на странице: {e}")
            return {}

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

    def update_odds_with_results(self, row, result):
        """Обновление котировок на основе результата"""
        try:
            # Проверяем, является ли результат матчем с овертаймом (по наличию скобок в event_name)
            event_name = row.get('event_name', '')
            is_overtime_match = '(' in event_name and ')' in event_name

            if is_overtime_match:
                # Для матчей с овертаймом ставим WIN в odds_x и LOSS в остальные
                row['odds_1'] = f"LOSS {row['odds_1']}"
                row['odds_x'] = f"WIN {row['odds_x']}"
                row['odds_2'] = f"LOSS {row['odds_2']}"

                # Для тоталов используем стандартную логику с корректным счетом
                score1, score2 = map(int, result.split(':'))
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

            # Стандартная обработка для обычных матчей
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

            # Обновляем тоталы
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

    def merge_csv_data(self, existing_data, new_data):
        """Объединение существующих данных с новыми"""
        try:
            # Создаем словарь для быстрого поиска по ключевым полям
            existing_dict = {}
            for row in existing_data:
                key = (row.get('event_name', ''), row.get('event_time', ''))
                existing_dict[key] = row

            # Обновляем существующие данные новыми
            for new_row in new_data:
                key = (new_row.get('event_name', ''), new_row.get('event_time', ''))
                if key in existing_dict:
                    # Обновляем существующую запись
                    existing_dict[key].update(new_row)
                else:
                    # Добавляем новую запись
                    existing_dict[key] = new_row

            # Возвращаем объединенный список
            return list(existing_dict.values())

        except Exception as e:
            logger.error(f"Ошибка при объединении данных: {e}")
            return new_data  # В случае ошибки возвращаем новые данные

    def process_csv_file(self, input_filename='nhl_odds.csv', output_filename='nhl_results_final.csv'):
        """Основной метод обработки CSV файла с сохранением существующих данных"""
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

                    # Используем существующие данные как основу
                    all_rows = existing_rows

                    # Добавляем колонку match_result если ее нет в существующих данных
                    if 'match_result' not in existing_fieldnames:
                        for row in all_rows:
                            row['match_result'] = ''
                        logger.info("Добавлена колонку match_result в существующие данные")
                except Exception as e:
                    logger.warning(f"Не удалось загрузить существующий файл {output_filename}: {e}")
                    all_rows = []
            else:
                logger.info(f"Выходной файл {output_filename} не существует, создаем новый")
                all_rows = []

            # Добавляем колонку для результатов если ее нет
            if 'match_result' not in fieldnames:
                fieldnames.append('match_result')

            # Принимаем cookies на первой странице
            self.navigate_to_date(datetime.now().date())  # Переходим на текущую дату для принятия cookies
            self.accept_cookies_if_present()

            # Создаем словарь для быстрого поиска существующих записей по уникальному ключу
            existing_dict = {}
            for row in all_rows:
                # Используем комбинацию event_name + event_time + parse_timestamp как уникальный ключ
                key = (
                    row.get('event_name', ''),
                    row.get('event_time', ''),
                    row.get('parse_timestamp', '')
                )
                existing_dict[key] = row

            # Группируем события по датам для оптимизации
            events_by_date = {}
            for i, row in enumerate(input_rows):
                # Пропускаем уже обработанные строки (с WIN/LOSS)
                if self.is_already_processed(row):
                    logger.info(f"Строка {i} уже обработана (есть WIN/LOSS) - пропускаем")
                    continue

                event_time = row['event_time']
                if not self.should_process_event(event_time):
                    logger.info(
                        f"Событие {event_time} не подходит для обработки (будущее, недавно началось или прошло более 3 дней)")
                    continue

                try:
                    # Извлекаем дату окончания события (дата, когда матч завершился)
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
            future_events_count = 0
            old_events_count = 0
            duplicate_count = 0

            # Обрабатываем события по датам
            for event_date, date_events in events_by_date.items():
                logger.info(f"Обработка даты: {event_date}, событий: {len(date_events)}")

                # Переходим на страницу с результатами для этой даты
                if self.navigate_to_date(event_date):
                    # Парсим ВСЕ результаты на этой дате
                    date_results = self.parse_all_match_results_on_page()

                    # Обновляем все события этой даты
                    for i, row in date_events:
                        event_name = row['event_name']
                        event_time = row['event_time']
                        parse_timestamp = row['parse_timestamp']

                        # Создаем уникальный ключ для поиска
                        key = (event_name, event_time, parse_timestamp)

                        # Дополнительная проверка на случай если строка уже обработана
                        if self.is_already_processed(row):
                            skipped_count += 1
                            logger.info(f"Строка {i} ({event_name}) уже обработана - пропускаем")
                            continue

                        # Ищем результат в распарсенных данных
                        result = None
                        new_event_name = event_name  # Сохраняем оригинальное название

                        if event_name in date_results:
                            result = date_results[event_name]
                            logger.info(f"Точное совпадение для: {event_name}")
                        else:
                            # Используем улучшенный поиск совпадений
                            best_match = self.find_best_match(event_name, date_results.keys())
                            if best_match:
                                result = date_results[best_match]
                                # Если нашли совпадение с овертаймом, обновляем event_name
                                if '(' in best_match and ')' in best_match:
                                    new_event_name = best_match
                                logger.info(f"Найдено совпадение для '{event_name}' -> '{best_match}'")

                        # Если результат не найден обычным способом, пробуем поиск через строку поиска
                        if not result:
                            logger.warning(f"Результат не найден обычным способом для: {event_name}")
                            logger.info(f"Пробуем поиск через строку поиска...")

                            search_results = self.search_event_by_name(event_name)
                            if search_results:
                                # Ищем в результатах поиска
                                if event_name in search_results:
                                    result = search_results[event_name]
                                    logger.info(f"Найден результат через поиск для: {event_name}")
                                else:
                                    # Используем улучшенный поиск совпадений в результатах поиска
                                    best_match = self.find_best_match(event_name, search_results.keys())
                                    if best_match:
                                        result = search_results[best_match]
                                        # Если нашли совпадение с овертаймом, обновляем event_name
                                        if '(' in best_match and ')' in best_match:
                                            new_event_name = best_match
                                        logger.info(
                                            f"Найдено совпадение через поиск для '{event_name}' -> '{best_match}'")

                        if result:
                            # Обновляем результат и event_name (если изменился)
                            row['match_result'] = result
                            row['event_name'] = new_event_name
                            # Обновляем котировки
                            updated_row = self.update_odds_with_results(row, result)

                            # Проверяем, существует ли уже такая запись
                            if key in existing_dict:
                                # Обновляем существующую запись (полностью заменяем)
                                existing_row = existing_dict[key]
                                existing_row.update(updated_row)
                                duplicate_count += 1
                                logger.info(f"Обновлена существующая запись: {new_event_name} - {result}")
                            else:
                                # Добавляем новую запись
                                all_rows.append(updated_row)
                                existing_dict[key] = updated_row

                            updated_count += 1
                            logger.info(f"Обновлено событие: {new_event_name} - {result}")
                        else:
                            logger.warning(f"Не удалось найти результат для: {event_name}")
                            # Проверяем, может быть матч еще не сыгран
                            current_date = datetime.now().date()
                            if event_date >= current_date:
                                logger.info(f"Матч {event_name} на дату {event_date} возможно еще не сыгран")
                                future_events_count += 1
                            else:
                                # Проверяем, не слишком ли старый матч
                                event_time_dt = datetime.strptime(event_time, "%d.%m.%Y %H:%M")
                                time_since_event = datetime.now() - event_time_dt
                                if time_since_event > timedelta(days=3):
                                    old_events_count += 1
                                    logger.info(f"Матч {event_name} слишком старый (более 3 дней) - пропускаем")
                            logger.warning(f"Доступные результаты: {list(date_results.keys())}")

                    # Небольшая пауза между датами
                    time.sleep(2)
                else:
                    logger.error(f"Не удалось перейти на дату {event_date}")

            # УДАЛЯЕМ ДУБЛИКАТЫ перед сохранением
            unique_rows = []
            seen_keys = set()

            for row in all_rows:
                key = (
                    row.get('event_name', ''),
                    row.get('event_time', ''),
                    row.get('parse_timestamp', '')
                )
                if key not in seen_keys:
                    seen_keys.add(key)
                    unique_rows.append(row)
                else:
                    logger.warning(f"Обнаружен дубликат и удален: {key}")

            # Сохраняем обновленные данные
            try:
                self.save_csv_data(output_filename, fieldnames, unique_rows)
                logger.info(f"Данные успешно сохранены в {output_filename}")
                logger.info(
                    f"Обработка завершена. Обновлено: {updated_count}, Пропущено (уже обработаны): {skipped_count}, "
                    f"Будущие события: {future_events_count}, События старше 3 дней: {old_events_count}, "
                    f"Обновлено дубликатов: {duplicate_count}, Удалено дубликатов: {len(all_rows) - len(unique_rows)}")
                logger.info(f"Всего уникальных записей в файле: {len(unique_rows)}")
                return updated_count

            except Exception as e:
                logger.error(f"Ошибка при сохранении файла: {e}")
                return 0

        except Exception as e:
            logger.error(f"Ошибка при обработке CSV файла: {e}")
            return 0

    def run(self):
        """Основной метод запуска парсера результатов"""
        try:
            logger.info("Запуск парсера результатов FonBet для НХЛ...")

            success = self.process_csv_file()

            if success is not False:
                print("✅ Парсинг результатов завершен успешно!")
                print("📊 Данные сохранены в файл nhl_results_final.csv")
                if success > 0:
                    print(f"🔄 Обновлено событий: {success}")
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
    print("🚀 Запуск парсера результатов FonBet для Национальной Хоккейной Лиги (НХЛ)")
    print("⏳ Инициализация...")

    parser = NhlResultsParser(headless=False)  # False - видимый режим для отладки
    parser.run()


if __name__ == "__main__":
    main()