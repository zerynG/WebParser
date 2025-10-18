import os
import sys
import django
from django.core.management.base import BaseCommand

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class Command(BaseCommand):
    help = 'Запуск парсера котировок НХЛ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Запуск в фоновом режиме (без браукзера)',
        )

    def handle(self, *args, **options):
        try:
            # Импортируем ваш парсер
            from NhlFonParser import NhlFonBetParser

            self.stdout.write('Запуск парсера котировок НХЛ...')

            # Создаем экземпляр парсера
            parser = NhlFonBetParser(headless=options['headless'])

            # Запускаем парсинг
            parser.run()

            self.stdout.write(self.style.SUCCESS('Парсинг котировок НХЛ завершен успешно!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при парсинге: {e}'))