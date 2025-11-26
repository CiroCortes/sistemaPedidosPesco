from django.urls import path
from . import views

app_name = 'solicitudes'

urlpatterns = [
    path('', views.lista_solicitudes, name='lista'),
    path('nueva/', views.crear_solicitud, name='crear'),
    path('<int:pk>/', views.detalle_solicitud, name='detalle'),
    path('<int:pk>/ajax/', views.detalle_solicitud_ajax, name='detalle_ajax'),
    # API para IA / MCP
    path('api/ia/crear/', views.api_crear_solicitud_ia, name='api_crear_ia'),
]

