from django.urls import path

from . import views

app_name = 'despacho'

urlpatterns = [
    path('gestion/', views.gestion_despacho, name='gestion'),
    path('bultos/crear/', views.crear_bulto, name='crear_bulto'),
    path('bultos/<int:pk>/', views.detalle_bulto, name='detalle_bulto'),
    path('bultos/<int:pk>/estado/', views.actualizar_estado_bulto, name='actualizar_estado_bulto'),
    path('solicitudes/<int:pk>/imprimir_bultos/', views.imprimir_bultos_solicitud, name='imprimir_bultos_solicitud'),
    path('bultos/lote/<str:ids>/', views.lote_bultos, name='lote_bultos'),
    path('bultos/lote/<str:ids>/imprimir/', views.imprimir_lote, name='imprimir_lote'),
]

