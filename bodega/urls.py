from django.urls import path
from . import views

app_name = 'bodega'

urlpatterns = [
    path('cargar/', views.cargar_stock, name='cargar_stock'),
    path('consultar/', views.consultar_stock, name='consultar_stock'),
    path('historial/', views.historial_cargas, name='historial_cargas'),
]
