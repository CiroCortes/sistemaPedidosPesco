from django.urls import path
from . import views, api_views

app_name = 'inventario'

urlpatterns = [
    path('cargar/', views.cargar_stock, name='cargar_stock'),
    path('consultar/', views.consultar_stock, name='consultar_stock'),
    
    # API Endpoints
    path('api/stock/<str:codigo>/', api_views.stock_producto, name='api_stock_producto'),
    path('api/stock/verificar-disponibilidad/', api_views.verificar_disponibilidad, name='api_verificar'),
]
