from django.contrib import admin

from .models import StockReserva, BodegaTransferencia


@admin.register(StockReserva)
class StockReservaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'bodega', 'cantidad', 'estado', 'solicitud')
    list_filter = ('estado', 'bodega')
    search_fields = ('codigo', 'solicitud__cliente')


@admin.register(BodegaTransferencia)
class BodegaTransferenciaAdmin(admin.ModelAdmin):
    list_display = ('numero_transferencia', 'codigo_detalle', 'bodega_origen', 'bodega_destino', 'cantidad', 'fecha_transferencia')
    search_fields = ('numero_transferencia', 'detalle__codigo', 'solicitud__cliente')
    list_filter = ('bodega_origen', 'bodega_destino', 'fecha_transferencia')

    def codigo_detalle(self, obj):
        return obj.detalle.codigo
    codigo_detalle.short_description = 'Código'
