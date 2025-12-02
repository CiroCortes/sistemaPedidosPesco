from django.apps import apps
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import SolicitudDetalle


def _get_stock_reserva_model():
    return apps.get_model('bodega', 'StockReserva')


@receiver(post_save, sender=SolicitudDetalle)
def crear_o_actualizar_reserva(sender, instance, created, **kwargs):
    """
    Crea o sincroniza la reserva de stock asociada a un detalle.
    """
    StockReserva = _get_stock_reserva_model()

    if not instance.bodega or not instance.codigo:
        # Si no hay datos suficientes, liberar cualquier reserva existente
        StockReserva.objects.filter(detalle=instance).update(estado='liberada')
        return

    defaults = {
        'solicitud': instance.solicitud,
        'codigo': instance.codigo,
        'bodega': instance.bodega,
        'cantidad': instance.cantidad,
    }

    reserva, fue_creada = StockReserva.objects.get_or_create(
        detalle=instance,
        defaults=defaults,
    )

    if not fue_creada:
        cambios = []
        for campo, valor in defaults.items():
            if getattr(reserva, campo) != valor:
                setattr(reserva, campo, valor)
                cambios.append(campo)
        if cambios:
            reserva.save(update_fields=cambios + ['updated_at'])

    # Si el detalle ya fue preparado, marcar la reserva como consumida
    if instance.estado_bodega == 'preparado' and reserva.estado != 'consumida':
        reserva.marcar_consumida()


@receiver(post_delete, sender=SolicitudDetalle)
def liberar_reserva(sender, instance, **kwargs):
    """
    Libera la reserva cuando se elimina el detalle.
    """
    StockReserva = _get_stock_reserva_model()
    StockReserva.objects.filter(detalle=instance).update(estado='liberada')

