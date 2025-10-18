from django.urls import path
from . import views

app_name = 'results'

urlpatterns = [
    path('nhl/', views.nhl_results, name='nhl_results'),
    path('khl/', views.khl_results, name='khl_results'),
]