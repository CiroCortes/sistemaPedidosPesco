"""
Muestra cuántas solicitudes hay por cada `estado` y compara con la suma de las
tarjetas del dashboard admin (pendiente, en_despacho, listo_despacho, despachado).

Las que "faltan" en esa suma suelen ser embalado, en_ruta, cancelado, u otros valores.

Uso:
  python manage.py desglose_estados_solicitudes
  python manage.py desglose_estados_solicitudes --migrar-embalado-a-listo --dry-run
  python manage.py desglose_estados_solicitudes --migrar-embalado-a-listo
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from solicitudes.models import Solicitud

# Misma lógica que las tarjetas KPI del dashboard admin (sin urgentes ni total).
ESTADOS_EN_TARJETAS = frozenset({
    'pendiente',
    'en_despacho',
    'listo_despacho',
    'despachado',
})


class Command(BaseCommand):
    help = 'Cuenta solicitudes por estado; opcional: migrar embalado a listo_despacho.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--migrar-embalado-a-listo',
            action='store_true',
            help='Pasa solicitudes en estado embalado a listo_despacho (flujo embalado inactivo).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Con --migrar-embalado-a-listo: no escribe en BD, solo muestra cuántas se moverían.',
        )

    def handle(self, *args, **options):
        total = Solicitud.objects.count()
        filas = (
            Solicitud.objects.values('estado')
            .annotate(n=Count('id'))
            .order_by('estado')
        )

        self.stdout.write(self.style.NOTICE(f'Total solicitudes: {total}\n'))
        self.stdout.write('Por estado:')
        suma_tarjetas = 0
        otros = []
        for row in filas:
            est = row['estado'] or '(vacío)'
            n = row['n']
            self.stdout.write(f'  {est!r}: {n}')
            if est in ESTADOS_EN_TARJETAS:
                suma_tarjetas += n
            else:
                otros.append((est, n))

        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                f'Suma tarjetas (pendiente + en_despacho + listo_despacho + despachado): {suma_tarjetas}'
            )
        )
        gap = total - suma_tarjetas
        if gap:
            self.stdout.write(self.style.WARNING(f'Diferencia vs total (no en esas 4 tarjetas): {gap}'))
            self.stdout.write('Desglose de esos estados:')
            for est, n in sorted(otros, key=lambda x: (-x[1], x[0])):
                self.stdout.write(f'  {est!r}: {n}')
        else:
            self.stdout.write(self.style.SUCCESS('Coincide con el total (no hay otros estados con filas).'))

        if not options['migrar_embalado_a_listo']:
            return

        self.stdout.write('')
        self.stdout.write(self.style.NOTICE('--- Migracion embalado -> listo_despacho ---'))
        antes = Solicitud.objects.filter(estado='embalado').count()
        if antes == 0:
            self.stdout.write(self.style.SUCCESS('Cambio aplicado: NO. No hay solicitudes en embalado.'))
            return

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY-RUN] Cambio aplicado: NO (solo simulacion). '
                    f'Se actualizarian {antes} solicitudes: embalado -> listo_despacho.'
                )
            )
            return

        ahora = timezone.now()
        actualizadas = Solicitud.objects.filter(estado='embalado').update(
            estado='listo_despacho',
            updated_at=ahora,
        )
        restantes = Solicitud.objects.filter(estado='embalado').count()
        if actualizadas > 0 and restantes == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Cambio aplicado: SI. {actualizadas} solicitud(es) pasaron de embalado a listo_despacho.'
                )
            )
        elif actualizadas > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'Se actualizaron {actualizadas} filas; aún quedan {restantes} en embalado (revisar condición de carrera).'
                )
            )
        else:
            self.stdout.write(self.style.ERROR('No se actualizó ninguna fila (inesperado si había embalado).'))
