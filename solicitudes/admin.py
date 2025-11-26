from django.contrib import admin
from .models import Solicitud


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    """
    Admin para el modelo Solicitud
    """
    list_display = ('id', 'fecha_solicitud', 'cliente', 'codigo', 'cantidad_solicitada', 'estado', 'urgente', 'solicitante')
    list_filter = ('estado', 'urgente', 'tipo', 'fecha_solicitud')
    search_fields = ('cliente', 'codigo', 'descripcion')
    date_hierarchy = 'fecha_solicitud'
    ordering = ('-fecha_solicitud', '-hora_solicitud')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('fecha_solicitud', 'hora_solicitud', 'tipo', 'cliente')
        }),
        ('Producto', {
            'fields': ('codigo', 'descripcion', 'cantidad_solicitada', 'bodega')
        }),
        ('Estado y Prioridad', {
            'fields': ('estado', 'urgente', 'observacion')
        }),
        ('Sistema', {
            'fields': ('solicitante', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('solicitante')
