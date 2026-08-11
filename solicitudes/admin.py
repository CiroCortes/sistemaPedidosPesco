from django.contrib import admin
from .models import Solicitud, SolicitudDetalle


class SolicitudDetalleInline(admin.TabularInline):
    model = SolicitudDetalle
    extra = 0
    fields = ('codigo', 'descripcion', 'cantidad', 'bodega', 'estado_bodega', 'preparado_por', 'fecha_preparacion')
    readonly_fields = ('preparado_por', 'fecha_preparacion')
    autocomplete_fields = ['preparado_por']


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
    
    inlines = [SolicitudDetalleInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('fecha_solicitud', 'hora_solicitud', 'tipo', 'cliente')
        }),
        ('Resumen', {
            'fields': ('codigo', 'descripcion', 'cantidad_solicitada')
        }),
        ('Transporte', {
            'fields': ('transporte', 'numero_pedido', 'numero_st')
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
