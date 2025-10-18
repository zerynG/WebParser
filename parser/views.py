from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import threading
import json
import os
from datetime import datetime


def control_panel(request):
    """Страница управления парсерами"""
    # Проверяем существование CSV файлов для отображения статуса
    file_info = {}

    # Определяем файлы для проверки
    files_to_check = {
        'nhl_odds': 'nhl_odds.csv',
        'nhl_results': 'nhl_results_final.csv',
        'khl_odds': 'khl_odds.csv',
        'khl_results': 'khl_results_final.csv',
    }

    for file_key, file_path in files_to_check.items():
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            file_info[file_key] = {
                'exists': True,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M'),
                'records': count_csv_records(file_path)
            }
        else:
            file_info[file_key] = {
                'exists': False,
                'size': 0,
                'modified': '-',
                'records': 0
            }

    context = {
        'file_info': file_info,
        'current_time': datetime.now().strftime('%H:%M:%S')
    }
    return render(request, 'parser/control_panel.html', context)


def count_csv_records(file_path):
    """Подсчет количества записей в CSV файле"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Вычитаем заголовок
            return max(0, len(lines) - 1)
    except:
        return 0


@csrf_exempt
def run_parser(request):
    """Запуск парсера через AJAX"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            parser_type = data.get('parser_type')
            headless = data.get('headless', False)

            # Определяем команду в зависимости от типа парсера
            command_map = {
                'nhl_odds': ['python', 'manage.py', 'parse_nhl_odds'],
                'nhl_results': ['python', 'manage.py', 'parse_nhl_results'],
                'khl_odds': ['python', 'manage.py', 'parse_khl_odds'],
                'khl_results': ['python', 'manage.py', 'parse_khl_results'],
            }

            if parser_type not in command_map:
                return JsonResponse({'status': 'error', 'message': 'Неизвестный тип парсера'})

            command = command_map[parser_type]

            # Добавляем флаг headless если нужно
            if headless:
                command.append('--headless')

            # Запускаем в отдельном потоке чтобы не блокировать ответ
            def run_parser_thread():
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        cwd='.'  # Рабочая директория проекта
                    )
                    print(f"Parser {parser_type} output: {result.stdout}")
                    if result.stderr:
                        print(f"Parser {parser_type} errors: {result.stderr}")
                except Exception as e:
                    print(f"Parser {parser_type} thread error: {e}")

            thread = threading.Thread(target=run_parser_thread)
            thread.daemon = True
            thread.start()

            return JsonResponse({
                'status': 'success',
                'message': f'Парсер {parser_type} запущен в фоновом режиме'
            })

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Only POST requests allowed'})