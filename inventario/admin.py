from django.contrib import admin
from .models import StockSAP, CargaStock


@admin.register(StockSAP)
class StockSAPAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion', 'bodega', 'stock_disponible', 'ubicacion', 'ultima_actualizacion')
    list_filter = ('bodega', 'descripcion_grupo', 'ultima_actualizacion')
    search_fields = ('codigo', 'descripcion', 'bodega', 'bodega_nombre')
    readonly_fields = ('ultima_actualizacion', 'created_at')
    list_per_page = 50
    
    fieldsets = (
        ('Información del Producto', {
            'fields': ('codigo', 'descripcion', 'categoria')
        }),
        ('Clasificación', {
            'fields': ('cod_grupo', 'descripcion_grupo')
        }),
        ('Bodega y Ubicación', {
            'fields': ('bodega', 'bodega_nombre', 'ubicacion', 'ubicacion_2')
        }),
        ('Stock y Precios', {
            'fields': ('stock_disponible', 'stock_reservado', 'precio', 'total')
        }),
        ('Metadata', {
            'fields': ('ultima_actualizacion', 'created_at')
        }),
    )


@admin.register(CargaStock)
class CargaStockAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_carga', 'usuario_id', 'nombre_archivo', 'total_productos', 'estado')
    list_filter = ('estado', 'fecha_carga')
    search_fields = ('nombre_archivo',)
    readonly_fields = ('fecha_carga', 'created_at')
    list_per_page = 25
    
    fieldsets = (
        ('Información de la Carga', {
            'fields': ('fecha_carga', 'usuario_id', 'nombre_archivo')
        }),
        ('Resultado', {
            'fields': ('estado', 'total_productos', 'total_bodegas', 'mensaje_error')
        }),
    )
    
    def has_add_permission(self, request):
        return False
