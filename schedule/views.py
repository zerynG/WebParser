import csv
import os
from django.shortcuts import render
from datetime import datetime


def nhl_schedule(request):
    """Вывод расписания НХЛ"""
    matches = []

    try:
        with open('nhl_odds.csv', 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Парсим время события
                try:
                    event_time = datetime.strptime(row['event_time'], '%d.%m.%Y %H:%M')
                    # Проверяем, что матч еще не сыгран (нет результата)
                    if 'match_result' not in row or not row['match_result']:
                        matches.append({
                            'event_name': row['event_name'],
                            'event_time': row['event_time'],
                            'formatted_time': event_time.strftime('%d.%m %H:%M'),
                            'odds_1': row.get('odds_1', ''),
                            'odds_x': row.get('odds_x', ''),
                            'odds_2': row.get('odds_2', ''),
                            'total_value': row.get('total_value', ''),
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
    return render(request, 'schedule/nhl_schedule.html', context)


def khl_schedule(request):
    """Вывод расписания КХЛ"""
    matches = []

    try:
        with open('khl_odds.csv', 'r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    event_time = datetime.strptime(row['event_time'], '%d.%m.%Y %H:%M')
                    # Проверяем, что матч еще не сыгран
                    if 'match_result' not in row or not row['match_result']:
                        matches.append({
                            'event_name': row['event_name'],
                            'event_time': row['event_time'],
                            'formatted_time': event_time.strftime('%d.%m %H:%M'),
                            'odds_1': row.get('odds_1', ''),
                            'odds_x': row.get('odds_x', ''),
                            'odds_2': row.get('odds_2', ''),
                            'total_value': row.get('total_value', ''),
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
    return render(request, 'schedule/khl_schedule.html', context)