from django.urls import path
from . import views

app_name = 'schedule'

urlpatterns = [
    path('nhl/', views.nhl_schedule, name='nhl_schedule'),
    path('khl/', views.khl_schedule, name='khl_schedule'),
]