from django.shortcuts import render

def home(request):
    context = {
        'title': 'Sports Parser - Главная',
    }
    return render(request, 'core/home.html', context)