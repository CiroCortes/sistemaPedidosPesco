"""
URL configuration for backend project - Sistema PESCO

Basado en la arquitectura de sistemaGDV
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core import views_bodegas, views_usuarios
from ia import views as ia_views
from diagnostico import views as diagnostico_views

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Core (autenticación y dashboard)
    path('', core_views.dashboard, name='dashboard'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('perfil/', core_views.perfil_usuario, name='perfil'),
    path('ia/chat/', ia_views.ia_chat, name='ia_chat'),
    
    # Gestión de Bodegas (Admin)
    path('bodegas/', views_bodegas.lista_bodegas, name='lista_bodegas'),
    path('bodegas/nueva/', views_bodegas.crear_bodega, name='crear_bodega'),
    path('bodegas/<int:pk>/editar/', views_bodegas.editar_bodega, name='editar_bodega'),
    path('bodegas/<int:pk>/toggle/', views_bodegas.toggle_estado_bodega, name='toggle_estado_bodega'),
    path('bodegas/usuarios/', views_bodegas.lista_usuarios_bodegas, name='lista_usuarios_bodegas'),
    path('bodegas/usuarios/<int:user_id>/asignar/', views_bodegas.asignar_bodegas, name='asignar_bodegas'),
    
    # Gestión de usuarios (Admin)
    path('usuarios/', views_usuarios.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views_usuarios.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:pk>/editar/', views_usuarios.editar_usuario, name='editar_usuario'),
    
    # Diagnóstico (Solo para admin/desarrollo)
    path('diagnostico/', diagnostico_views.pagina_diagnostico, name='diagnostico'),
    
    # Apps del sistema (se crearán sus urls.py)
    path('solicitudes/', include('solicitudes.urls')),
    path('bodega/', include('bodega.urls')),
    path('inventario/', include('inventario.urls')),  # URLs de inventario
    path('despacho/', include('despacho.urls')),
    path('configuracion/', include('configuracion.urls')),
    path('reportes/', include('reportes.urls')),
    path('guias/', include('guias.urls')),
    
    # API (opcional)
    # path('api/', include('api.urls')),
]

# Servir archivos media y static en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Personalizar el admin
admin.site.site_header = "Sistema PESCO - Administración"
admin.site.site_title = "PESCO Admin"
admin.site.index_title = "Bienvenido al Panel de Administración"
