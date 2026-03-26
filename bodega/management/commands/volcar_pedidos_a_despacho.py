"""
Vuelco demo: marca como preparados todos los detalles pendientes que NO son bodega 013,
crea BodegaTransferencia con N° aleatorio de 5 dígitos (uno por pedido) y pone la solicitud en en_despacho.
NO llama mover_stock ni depende de ubicaciones/stock.

Uso:
  python manage.py volcar_pedidos_a_despacho
  python manage.py volcar_pedidos_a_despacho --dry-run
  python manage.py volcar_pedidos_a_despacho --limite 50
"""

import random
from collections import defaultdict
from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bodega.models import BodegaTransferencia
from solicitudes.models import Solicitud, SolicitudDetalle


def _random_5_digits() -> str:
    return f'{random.randint(0, 99999):05d}'


class Command(BaseCommand):
    help = (
        'Pasa a preparado los detalles (≠ bodega 013), crea transferencia demo 5 dígitos y solicitud → en_despacho. '
        'Sin mover_stock.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué haría, sin guardar')
        parser.add_argument('--limite', type=int, default=None, help='Máximo de solicitudes a procesar')
        parser.add_argument(
            '--min-min-entre-lineas',
            type=int,
            default=10,
            help='Minutos mínimos aleatorios entre fecha_preparacion de líneas del mismo pedido',
        )
        parser.add_argument(
            '--max-min-entre-lineas',
            type=int,
            default=25,
            help='Minutos máximos aleatorios entre líneas del mismo pedido',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limite = options['limite']
        lo = options['min_min_entre_lineas']
        hi = options['max_min_entre_lineas']
        if lo > hi:
            lo, hi = hi, lo

        qs = (
            SolicitudDetalle.objects.filter(estado_bodega__in=['pendiente', 'preparando'])
            .exclude(bodega='013')
            .select_related('solicitud')
            .order_by('solicitud_id', 'id')
        )

        por_solicitud: dict[int, list] = defaultdict(list)
        for d in qs:
            por_solicitud[d.solicitud_id].append(d)

        items = list(por_solicitud.items())
        if limite is not None:
            items = items[: limite]

        total_detalles = sum(len(v) for _, v in items)
        self.stdout.write(f'Solicitudes afectadas: {len(items)} | Detalles a preparar: {total_detalles}')

        if dry_run:
            for sid, detalles in items[:20]:
                s = detalles[0].solicitud
                self.stdout.write(
                    f'  [DRY] #{sid} pedido={s.numero_pedido or s.numero_st} cliente={s.cliente[:40]} líneas={len(detalles)}'
                )
            if len(items) > 20:
                self.stdout.write(f'  ... y {len(items) - 20} solicitudes más')
            self.stdout.write(self.style.WARNING('Dry-run: no se modificó la base de datos.'))
            return

        detalles_hechos = 0
        solicitudes_en_despacho = 0

        for solicitud_id, detalles in items:
            solicitud = detalles[0].solicitud
            numero_tr = _random_5_digits()
            acum_min = 0
            base = timezone.now()

            try:
                with transaction.atomic():
                    for detalle in detalles:
                        fecha_prep = base + timedelta(minutes=acum_min)
                        acum_min += random.randint(lo, hi)

                        bodega_origen = (detalle.bodega or '').strip() or 'N/D'
                        lt = timezone.localtime(fecha_prep)
                        try:
                            reserva_obj = detalle.reserva
                        except ObjectDoesNotExist:
                            reserva_obj = None

                        BodegaTransferencia.objects.create(
                            solicitud=solicitud,
                            detalle=detalle,
                            reserva=reserva_obj,
                            numero_transferencia=numero_tr,
                            fecha_transferencia=lt.date(),
                            hora_transferencia=lt.time(),
                            bodega_origen=bodega_origen,
                            bodega_destino='013',
                            cantidad=detalle.cantidad,
                            registrado_por=None,
                            observaciones='Vuelco demo automático (sin stock)',
                        )

                        if reserva_obj:
                            try:
                                reserva_obj.marcar_consumida()
                            except Exception:
                                pass

                        detalle.estado_bodega = 'preparado'
                        detalle.preparado_por = None
                        detalle.fecha_preparacion = fecha_prep
                        detalle.save(
                            update_fields=['estado_bodega', 'preparado_por', 'fecha_preparacion']
                        )
                        detalles_hechos += 1

                    solicitud.refresh_from_db()
                    pend = solicitud.detalles.exclude(bodega='013').exclude(estado_bodega='preparado')
                    if not pend.exists():
                        if solicitud.estado != 'en_despacho':
                            solicitud.estado = 'en_despacho'
                            solicitud.save(update_fields=['estado'])
                            solicitudes_en_despacho += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error solicitud #{solicitud_id}: {e}'))
                continue

        self.stdout.write(self.style.SUCCESS(f'Detalles preparados: {detalles_hechos}'))
        self.stdout.write(self.style.SUCCESS(f'Solicitudes pasadas a en_despacho: {solicitudes_en_despacho}'))
