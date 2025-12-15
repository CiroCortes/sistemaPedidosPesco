from django.urls import path
from . import views

app_name = 'reportes'

urlpatterns = [
    path('informe-completo/', views.informe_completo, name='informe_completo'),
]

