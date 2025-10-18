import csv
import os
from django.shortcuts import render
from datetime import datetime


def nhl_results(request):
    """Вывод результатов НХЛ"""
    matches = []

    try:
        with open('nhl_results_final.csv', 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Парсим время события
                try:
                    event_time = datetime.strptime(row['event_time'], '%d.%m.%Y %H:%M')
                    # Проверяем, что матч имеет результат
                    if row.get('match_result') and row['match_result'].strip():
                        # Определяем тип матча (обычный или овертайм)
                        is_overtime = '(' in row['event_name'] and ')' in row['event_name']

                        matches.append({
                            'event_name': row['event_name'],
                            'event_time': row['event_time'],
                            'formatted_time': event_time.strftime('%d.%m %H:%M'),
                            'match_result': row['match_result'],
                            'is_overtime': is_overtime,
                            'odds_1': row.get('odds_1', ''),
                            'odds_x': row.get('odds_x', ''),
                            'odds_2': row.get('odds_2', ''),
                            'total_over': row.get('total_over', ''),
                            'total_under': row.get('total_under', ''),
                        })
                except ValueError:
                    continue

        # Сортируем по дате в обратном порядке (свежие сверху)
        matches.sort(key=lambda x: datetime.strptime(x['event_time'], '%d.%m.%Y %H:%M'), reverse=True)

    except FileNotFoundError:
        matches = []

    context = {
        'matches': matches,
        'total_matches': len(matches),
        'league': 'НХЛ',
    }
    return render(request, 'results/nhl_results.html', context)


def khl_results(request):
    """Вывод результатов КХЛ"""
    matches = []

    try:
        with open('khl_results_final.csv', 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    event_time = datetime.strptime(row['event_time'], '%d.%m.%Y %H:%M')
                    # Проверяем, что матч имеет результат
                    if row.get('match_result') and row['match_result'].strip():
                        is_overtime = '(' in row['event_name'] and ')' in row['event_name']

                        matches.append({
                            'event_name': row['event_name'],
                            'event_time': row['event_time'],
                            'formatted_time': event_time.strftime('%d.%m %H:%M'),
                            'match_result': row['match_result'],
                            'is_overtime': is_overtime,
                            'odds_1': row.get('odds_1', ''),
                            'odds_x': row.get('odds_x', ''),
                            'odds_2': row.get('odds_2', ''),
                            'total_over': row.get('total_over', ''),
                            'total_under': row.get('total_under', ''),
                        })
                except ValueError:
                    continue

        # Сортируем по дате в обратном порядке (свежие сверху)
        matches.sort(key=lambda x: datetime.strptime(x['event_time'], '%d.%m.%Y %H:%M'), reverse=True)

    except FileNotFoundError:
        matches = []

    context = {
        'matches': matches,
        'total_matches': len(matches),
        'league': 'КХЛ',
    }
    return render(request, 'results/khl_results.html', context)