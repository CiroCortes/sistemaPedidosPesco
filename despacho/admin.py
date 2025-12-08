from django.contrib import admin

from .models import Bulto


@admin.register(Bulto)
class BultoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'solicitud', 'estado', 'transportista', 'peso_total', 'fecha_creacion', 'total_detalles')
    list_filter = ('estado', 'transportista')
    search_fields = ('codigo', 'numero_guia_transportista', 'solicitud__cliente', 'solicitud__id')
    list_select_related = ('solicitud',)

    def total_detalles(self, obj):
        return obj.detalles.count()
    total_detalles.short_description = 'Códigos'


# Modelo BultoSolicitud eliminado - ahora la relación es directa mediante ForeignKey
# @admin.register(BultoSolicitud)
# class BultoSolicitudAdmin(admin.ModelAdmin):
#     list_display = ('bulto', 'solicitud', 'created_at')
#     search_fields = ('bulto__codigo', 'solicitud__cliente')
