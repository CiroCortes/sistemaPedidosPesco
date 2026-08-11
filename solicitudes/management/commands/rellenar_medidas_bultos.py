"""
Asigna peso y dimensiones a bultos que aún tienen medidas en cero (p. ej. datos
cargados antes de enriquecer seed_demo_mes). No borra solicitudes.

Uso:
  python manage.py rellenar_medidas_bultos --dry-run
  python manage.py rellenar_medidas_bultos
"""

from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.db.models import Q

from despacho.models import Bulto

# Misma lógica que el dashboard: hace falta las tres dimensiones > 0.


def _medidas():
    largo = Decimal(str(random.randint(42, 115)))
    ancho = Decimal(str(random.randint(38, 88)))
    alto = Decimal(str(random.randint(32, 78)))
    vol_kg = (largo * ancho * alto) / Decimal('6000')
    peso_real = Decimal(str(round(random.uniform(7.0, 40.0), 2)))
    peso_total = max(peso_real, vol_kg * Decimal('0.85'))
    return {
        'largo_cm': largo,
        'ancho_cm': ancho,
        'alto_cm': alto,
        'peso_total': peso_total.quantize(Decimal('0.01')),
    }


class Command(BaseCommand):
    help = 'Rellena largo/ancho/alto/peso en bultos sin medidas (dashboard kilos volumétricos).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        qs = Bulto.objects.filter(
            Q(largo_cm__lte=0) | Q(ancho_cm__lte=0) | Q(alto_cm__lte=0)
        )
        n = qs.count()
        self.stdout.write(f'Bultos sin medidas útiles: {n}' + (' | DRY-RUN' if dry else ''))
        if dry or n == 0:
            return
        actualizados = 0
        for b in qs.iterator(chunk_size=200):
            m = _medidas()
            Bulto.objects.filter(pk=b.pk).update(**m)
            actualizados += 1
        self.stdout.write(self.style.SUCCESS(f'Actualizados: {actualizados} bultos.'))

