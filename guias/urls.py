from django.urls import path
from . import views

app_name = 'guias'

urlpatterns = [
    path('', views.emision_guias, name='emision_guias'),
    path('generar/', views.generar_detalle_guia, name='generar_detalle_guia'),
]

