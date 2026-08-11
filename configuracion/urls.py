from django.urls import path

from . import views

app_name = 'configuracion'

urlpatterns = [
    path('estados/', views.lista_estados, name='lista_estados'),
    path('estados/nuevo/', views.crear_estado, name='crear_estado'),
    path('estados/<int:pk>/editar/', views.editar_estado, name='editar_estado'),
    path('estados/<int:pk>/toggle/', views.toggle_estado, name='toggle_estado'),
    path('transportes/', views.lista_transportes, name='lista_transportes'),
    path('transportes/nuevo/', views.crear_transporte, name='crear_transporte'),
    path('transportes/<int:pk>/editar/', views.editar_transporte, name='editar_transporte'),
    path('transportes/<int:pk>/toggle/', views.toggle_transporte, name='toggle_transporte'),
    path('tipos-solicitud/', views.lista_tipos_solicitud, name='lista_tipos_solicitud'),
    path('tipos-solicitud/nuevo/', views.crear_tipo_solicitud, name='crear_tipo_solicitud'),
    path('tipos-solicitud/<int:pk>/editar/', views.editar_tipo_solicitud, name='editar_tipo_solicitud'),
    path('tipos-solicitud/<int:pk>/toggle/', views.toggle_tipo_solicitud, name='toggle_tipo_solicitud'),
    path('tipos-solicitud/<int:pk>/eliminar/', views.eliminar_tipo_solicitud, name='eliminar_tipo_solicitud'),
]

