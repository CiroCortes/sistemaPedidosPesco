from django.contrib import admin

from .models import Bulto, BultoSolicitud


@admin.register(Bulto)
class BultoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'estado', 'transportista', 'peso_total', 'fecha_creacion', 'total_detalles')
    list_filter = ('estado', 'transportista')
    search_fields = ('codigo', 'numero_guia_transportista')

    def total_detalles(self, obj):
        return obj.detalles.count()
    total_detalles.short_description = 'Códigos'


@admin.register(BultoSolicitud)
class BultoSolicitudAdmin(admin.ModelAdmin):
    list_display = ('bulto', 'solicitud', 'created_at')
    search_fields = ('bulto__codigo', 'solicitud__cliente')
