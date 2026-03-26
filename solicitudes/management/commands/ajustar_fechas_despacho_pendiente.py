"""
Recalcula solo fechas de solicitudes pendientes en despacho para que el dashboard
(no algoritmo) muestre horas laborales acotadas respecto a "ahora".

El widget "Solicitudes en Despacho (Listo para Despacho)" usa
calcular_horas_laborales(fecha_preparacion_más_reciente, timezone.now()).
Si fecha_preparacion quedó en febrero y hoy es marzo, las horas explotan.
Este comando mueve fecha_preparacion (y alinea fecha_embalaje de bultos) hacia
el presente, sin tocar estados ni transporte.

Uso:
  python manage.py ajustar_fechas_despacho_pendiente --dry-run
  python manage.py ajustar_fechas_despacho_pendiente --max-horas 48
  python manage.py ajustar_fechas_despacho_pendiente --estados listo_despacho,en_despacho
"""

import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from despacho.models import Bulto
from solicitudes.models import Solicitud, SolicitudDetalle


def _pick_fecha_preparacion(ahora, max_horas: float, rng: random.Random):
    """
    Elige fecha_preparacion en el pasado reciente tal que
    calcular_horas_laborales(fp, ahora) <= max_horas y cercana a un objetivo aleatorio.
    """
    from core.views import calcular_horas_laborales

    target = rng.uniform(6.0, min(47.0, max_horas - 1.0))
    lo = ahora - timedelta(days=21)
    hi = ahora - timedelta(minutes=2)

    for _ in range(64):
        if hi - lo < timedelta(minutes=1):
            break
        mid = lo + (hi - lo) / 2
        lab = calcular_horas_laborales(mid, ahora)
        if lab > target:
            lo = mid
        else:
            hi = mid

    fp = hi
    if calcular_horas_laborales(fp, ahora) > max_horas:
        fp = ahora - timedelta(minutes=5)
    if fp >= ahora:
        fp = ahora - timedelta(minutes=5)
    return fp


class Command(BaseCommand):
    help = (
        'Ajusta fecha_preparacion (y fecha_embalaje de bultos) para solicitudes en '
        'listo_despacho / en_despacho de modo que las horas laborales vs ahora no superen un tope.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-horas',
            type=float,
            default=48.0,
            help='Tope de horas laborales (misma función que el dashboard)',
        )
        parser.add_argument(
            '--estados',
            type=str,
            default='listo_despacho',
            help='Comma-separated: listo_despacho, en_despacho',
        )
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument(
            '--seed',
            type=int,
            default=None,
            help='Semilla RNG para fechas reproducibles',
        )

    def handle(self, *args, **options):
        max_horas = options['max_horas']
        dry = options['dry_run']
        seed = options['seed']
        rng = random.Random(seed) if seed is not None else random.Random()

        raw_estados = [x.strip() for x in options['estados'].split(',') if x.strip()]
        valid = {'listo_despacho', 'en_despacho'}
        estados = [e for e in raw_estados if e in valid]
        bad = set(raw_estados) - valid
        if bad:
            self.stderr.write(self.style.WARNING(f'Estados ignorados (no válidos): {bad}'))
        if not estados:
            self.stderr.write(self.style.ERROR('Ningún estado válido. Use listo_despacho y/o en_despacho.'))
            return

        ahora = timezone.now()

        qs = (
            Solicitud.objects.filter(estado__in=estados)
            .prefetch_related('detalles', 'bultos')
            .order_by('id')
        )
        total_sol = qs.count()
        if total_sol == 0:
            self.stdout.write(self.style.WARNING('No hay solicitudes en esos estados.'))
            return

        self.stdout.write(
            f'Solicitudes a ajustar: {total_sol} | estados={estados} | tope horas laborales={max_horas}'
            + (' | DRY-RUN' if dry else '')
        )

        n_ok = 0
        for sol in qs.iterator(chunk_size=100):
            fp_new = _pick_fecha_preparacion(ahora, max_horas, rng)

            if dry:
                n_ok += 1
                continue

            with transaction.atomic():
                det_ids = [d.pk for d in sol.detalles.all()]
                if det_ids:
                    SolicitudDetalle.objects.filter(pk__in=det_ids).update(fecha_preparacion=fp_new)

                for b in sol.bultos.all():
                    emb = fp_new + timedelta(hours=rng.uniform(0.5, 4.0))
                    if emb >= ahora:
                        emb = ahora - timedelta(minutes=3)
                    Bulto.objects.filter(pk=b.pk).update(fecha_embalaje=emb)
            n_ok += 1

        self.stdout.write(self.style.SUCCESS(f'Procesadas: {n_ok} solicitudes.'))

