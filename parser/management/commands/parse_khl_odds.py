import os
import sys
import django
from django.core.management.base import BaseCommand

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


class Command(BaseCommand):
    help = 'Запуск парсера котировок КХЛ'

    def add_arguments(self, parser):
        parser.add_argument(
            '--headless',
            action='store_true',
            help='Запуск в фоновом режиме (без браузера)',
        )

    def handle(self, *args, **options):
        try:
            # Импортируем ваш парсер КХЛ
            from KhlFonParser import KhlFonBetParser

            self.stdout.write('Запуск парсера котировок КХЛ...')

            # Создаем экземпляр парсера
            parser = KhlFonBetParser(headless=options['headless'])

            # Запускаем парсинг
            parser.run()

            self.stdout.write(self.style.SUCCESS('Парсинг котировок КХЛ завершен успешно!'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при парсинге КХЛ: {e}'))