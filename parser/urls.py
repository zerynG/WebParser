from django.urls import path
from . import views

app_name = 'parser'

urlpatterns = [
    path('', views.control_panel, name='control_panel'),
    path('run/', views.run_parser, name='run_parser'),
]