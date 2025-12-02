from django.urls import path
from django.urls import path
from . import views

app_name = 'solicitudes'

urlpatterns = [
    path('', views.lista_solicitudes, name='lista'),
    path('crear/', views.crear_solicitud, name='crear'),
    path('<int:pk>/', views.detalle_solicitud, name='detalle'),
    path('<int:pk>/editar/', views.editar_solicitud, name='editar'),
    path('<int:pk>/cambiar-estado/', views.cambiar_estado_solicitud, name='cambiar_estado'),
    path('<int:pk>/afecta-stock/', views.cambiar_afecta_stock, name='cambiar_afecta_stock'),
    path('detalle-ajax/<int:pk>/', views.detalle_solicitud_ajax, name='detalle_ajax'),
    path('detalle/<int:detalle_id>/preparar/', views.preparar_producto, name='preparar_producto'),
    # API para búsqueda de códigos en stock
    path('api/buscar-codigo/', views.buscar_codigo_stock, name='buscar_codigo'),
    # API para IA / MCP
    path('api/ia/crear/', views.api_crear_solicitud_ia, name='api_crear_ia'),
]
