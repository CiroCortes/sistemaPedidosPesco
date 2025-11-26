"""
URL configuration for backend project - Sistema PESCO

Basado en la arquitectura de sistemaGDV
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from ia import views as ia_views

urlpatterns = [
    # Admin de Django
    path('admin/', admin.site.urls),
    
    # Core (autenticación y dashboard)
    path('', core_views.dashboard, name='dashboard'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('perfil/', core_views.perfil_usuario, name='perfil'),
    path('ia/chat/', ia_views.ia_chat, name='ia_chat'),
    
    # Apps del sistema (se crearán sus urls.py)
    path('solicitudes/', include('solicitudes.urls')),
    path('bodega/', include('bodega.urls')),
    # path('despacho/', include('despacho.urls')),
    # path('guias/', include('guias.urls')),
    # path('reportes/', include('reportes.urls')),
    
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
