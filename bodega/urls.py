from django.urls import path
from . import views

app_name = 'bodega'

urlpatterns = [
    path('cargar/', views.cargar_stock, name='cargar_stock'),
    path('consultar/', views.consultar_stock, name='consultar_stock'),
    path('historial/', views.historial_cargas, name='historial_cargas'),
    path('pedidos/', views.gestion_pedidos, name='gestion_pedidos'),
    path('pedidos/<int:detalle_id>/transferir/', views.registrar_transferencia, name='registrar_transferencia'),
    path('pedidos/transferir-multiple/', views.registrar_transferencia_multiple, name='registrar_transferencia_multiple'),
]
