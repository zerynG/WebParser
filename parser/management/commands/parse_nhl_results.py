import os
import sys
import django
from django.core.management.base import BaseCommand

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class Command(BaseCommand):
    help = 'Запуск парсера результатов НХЛ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Запуск в фоновом режиме (без браузера)',
        )

    def handle(self, *args, **options):
        try:
            # Импортируем ваш парсер результатов НХЛ
            from NhlFonResParser import NhlResultsParser

            self.stdout.write('Запуск парсера результатов НХЛ...')

            # Создаем экземпляр парсера
            parser = NhlResultsParser(headless=options['headless'])

            # Запускаем парсинг
            parser.run()

            self.stdout.write(self.style.SUCCESS('Парсинг результатов НХЛ завершен успешно!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при парсинге результатов НХЛ: {e}'))