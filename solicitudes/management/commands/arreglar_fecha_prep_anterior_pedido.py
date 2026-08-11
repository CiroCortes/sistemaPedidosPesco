"""
Corrige SolicitudDetalle con fecha_preparacion anterior al inicio efectivo del pedido
(caso típico del seed antiguo: prep 08:02 vs pedido 16:50 el mismo día → lead time negativo).

Pone fecha_preparacion = inicio_efectivo + delta aleatorio corto (30–180 min).

Uso:
  python manage.py arreglar_fecha_prep_anterior_pedido --dry-run
  python manage.py arreglar_fecha_prep_anterior_pedido
"""

from datetime import timedelta
import random

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.views import inicio_efectivo_lead_time
from solicitudes.models import SolicitudDetalle

_CHILE = timezone.get_current_timezone()


class Command(BaseCommand):
    help = 'Alinea fecha_preparacion después del inicio del pedido cuando quedó incoherente.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = SolicitudDetalle.objects.filter(fecha_preparacion__isnull=False).select_related(
            'solicitud'
        )
        corregidos = 0
        for det in qs.iterator(chunk_size=500):
            sol = det.solicitud
            ini = inicio_efectivo_lead_time(sol)
            if not ini:
                continue
            fp = det.fecha_preparacion
            if timezone.is_naive(fp):
                fp = timezone.make_aware(fp, _CHILE)
            if timezone.is_naive(ini):
                ini = timezone.make_aware(ini, _CHILE)
            if fp >= ini:
                continue
            nuevo = ini + timedelta(minutes=random.randint(30, 180))
            if dry:
                corregidos += 1
                continue
            SolicitudDetalle.objects.filter(pk=det.pk).update(fecha_preparacion=nuevo)
            corregidos += 1

        msg = f'Detalles a corregir: {corregidos}' if dry else f'Detalles corregidos: {corregidos}'
        self.stdout.write(self.style.SUCCESS(msg))

