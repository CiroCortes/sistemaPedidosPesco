"""
Agrega solicitudes activas de demo (listo_despacho, embalado, en_despacho, pendiente)
en los últimos 1-3 días, SIN borrar nada de lo existente.

Útil para poblar el indicador "Solicitudes en Despacho" del dashboard sin tener
que resetear toda la base de datos.

Uso:
  python manage.py seed_activos_demo
  python manage.py seed_activos_demo --total 12
  python manage.py seed_activos_demo --dry-run
"""

import random
from datetime import timedelta, datetime, time
from decimal import Decimal

import pytz
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import Bodega
from bodega.models import Stock
from despacho.models import Bulto
from solicitudes.models import Solicitud, SolicitudDetalle

User = get_user_model()

CLIENTES = [
    'SUC CALAMA', 'SUC ANTOFAGASTA', 'SUC PTO MONTT', 'SUC LOS ANGELES',
    'INTUB SPA', 'STARCO S.A.', 'PROS', 'COMERCIAL NORTE',
    'TALLER HMS', 'TALLER OLEOHTECH', 'AGRO SUR', 'TRANS IMPORT',
]

# Estados activos con su distribución realista
ESTADOS_ACTIVOS = [
    ('listo_despacho', 0.45),
    ('en_despacho',    0.30),
    ('embalado',       0.15),
    ('pendiente',      0.10),
]

TRANSPORTES = ['PESCO', 'STARKEN', 'ESTAFETA', 'RETIRA_CLIENTE', 'VARMONTT']

BODEGAS_KPI = (
    '013-01', '013-03', '013-05', '013-08', '013-09', '013-PP', '013-PS',
)


def _hora_random():
    return time(random.randint(8, 17), random.randint(0, 59), 0)


def _elegir_estado_activo():
    r = random.random()
    acum = 0.0
    for est, p in ESTADOS_ACTIVOS:
        acum += p
        if r <= acum:
            return est
    return 'listo_despacho'


def _medidas_bulto():
    largo = Decimal(str(random.randint(42, 115)))
    ancho = Decimal(str(random.randint(38, 88)))
    alto  = Decimal(str(random.randint(32, 78)))
    vol_kg = (largo * ancho * alto) / Decimal('6000')
    peso_real = Decimal(str(round(random.uniform(7.0, 40.0), 2)))
    peso_total = max(peso_real, vol_kg * Decimal('0.85'))
    return {
        'largo_cm': largo,
        'ancho_cm': ancho,
        'alto_cm':  alto,
        'peso_total': peso_total.quantize(Decimal('0.01')),
    }


def _cursor_prep(ts):
    return ts + timedelta(minutes=random.randint(8, 120), seconds=random.randint(0, 59))


class Command(BaseCommand):
    help = 'Agrega solicitudes activas demo (listo_despacho/en_despacho/etc.) sin borrar datos existentes.'

    def add_arguments(self, parser):
        parser.add_argument('--total',   type=int, default=10,
                            help='Cantidad de solicitudes activas a crear (default: 10)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra lo que haría sin tocar la base de datos')

    def handle(self, *args, **options):
        total   = options['total']
        dry     = options['dry_run']
        chile   = pytz.timezone('America/Santiago')
        hoy     = timezone.localdate()

        # Bodegas activas
        bodegas_activas = list(
            Bodega.objects.filter(activa=True)
            .exclude(codigo='013')
            .values_list('codigo', flat=True)
        )
        if not bodegas_activas:
            self.stdout.write(self.style.ERROR('No hay bodegas activas.'))
            return

        # Pool de stock
        pool = list(
            Stock.objects.filter(bodega__in=bodegas_activas, stock_disponible__gt=0)
            .values('codigo', 'bodega', 'descripcion')[:300]
        )
        if len(pool) < 5:
            self.stdout.write(self.style.ERROR('Stock insuficiente en bodegas activas.'))
            return

        if dry:
            self.stdout.write(f'[DRY] Bodegas: {bodegas_activas}')
            self.stdout.write(f'[DRY] Pool stock: {len(pool)} filas')
            self.stdout.write(f'[DRY] Solicitudes activas a crear: {total} (últimos 1-3 días)')
            return

        admin = (
            User.objects.filter(rol='admin').first()
            or User.objects.filter(is_superuser=True).first()
        )

        creadas = 0

        for i in range(total):
            estado = _elegir_estado_activo()
            # Distribuir en los últimos 1-3 días (nunca hoy: evita timestamps futuros
            # si la hora aleatoria aún no llegó en el reloj real).
            dias_atras = random.randint(1, 3)
            dia = hoy - timedelta(days=dias_atras)

            hr_sol = _hora_random()
            cliente = random.choice(CLIENTES)
            tipo = random.choices(['PC', 'OF', 'ST'], weights=[78, 14, 8], k=1)[0]
            n_lineas = random.randint(1, 3)
            bodega_kpi = random.choice(BODEGAS_KPI)
            transporte = random.choice(TRANSPORTES)

            lineas = []
            for _ in range(n_lineas):
                row = random.choice(pool)
                lineas.append({
                    'codigo':      row['codigo'],
                    'bodega':      row['bodega'],
                    'descripcion': (row.get('descripcion') or f"Item {row['codigo']}")[:500],
                    'cantidad':    random.randint(1, 6),
                })
            primera = lineas[0]

            numero_pedido = ''
            if tipo != 'ST':
                numero_pedido = f'DEMO-ACT-{dia.strftime("%Y%m%d")}-{i+1:03d}'

            num_ot = ''
            if estado in ('en_despacho', 'embalado', 'listo_despacho') and random.random() > 0.5:
                num_ot = str(random.randint(100000, 999999))

            with transaction.atomic():
                ts_sol = chile.localize(datetime.combine(dia, hr_sol))

                s = Solicitud(
                    tipo=tipo,
                    numero_pedido=numero_pedido,
                    cliente=cliente,
                    fecha_solicitud=dia,
                    hora_solicitud=hr_sol,
                    bodega=bodega_kpi,
                    transporte=transporte,
                    estado=estado,
                    urgente=random.random() < 0.10,
                    codigo=primera['codigo'],
                    descripcion=primera['descripcion'],
                    cantidad_solicitada=sum(x['cantidad'] for x in lineas),
                    observacion='Pedido demo seed_activos_demo',
                    solicitante=admin,
                    afecta_stock=True,
                    numero_ot=num_ot,
                )
                s.save()
                Solicitud.objects.filter(pk=s.pk).update(created_at=ts_sol, updated_at=ts_sol)

                # Crear detalles con fecha_preparacion
                prep_cursor = ts_sol
                for prod in lineas:
                    prep_cursor = _cursor_prep(prep_cursor)
                    bod_kpi = random.choice(BODEGAS_KPI)
                    SolicitudDetalle.objects.create(
                        solicitud=s,
                        codigo=prod['codigo'],
                        descripcion=prod['descripcion'],
                        cantidad=prod['cantidad'],
                        bodega=bod_kpi,
                        estado_bodega='preparado',
                        preparado_por=admin,
                        fecha_preparacion=prep_cursor,
                    )

                fechas_prep = [
                    d.fecha_preparacion for d in s.detalles.all() if d.fecha_preparacion
                ]
                base_prep = max(fechas_prep) if fechas_prep else ts_sol

                # Crear bulto y grabar timestamps de transición en Solicitud
                if estado == 'listo_despacho':
                    b = Bulto.objects.create(
                        solicitud=s,
                        transportista=transporte,
                        estado='listo_despacho',
                        creado_por=admin,
                        **_medidas_bulto(),
                    )
                    SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                    emb = base_prep + timedelta(hours=random.randint(1, 6))
                    Bulto.objects.filter(pk=b.pk).update(fecha_embalaje=emb)
                    Solicitud.objects.filter(pk=s.pk).update(
                        fecha_en_despacho=base_prep,
                        fecha_listo_despacho=emb,
                    )

                elif estado == 'embalado':
                    b = Bulto.objects.create(
                        solicitud=s,
                        transportista=transporte,
                        estado='embalado',
                        creado_por=admin,
                        **_medidas_bulto(),
                    )
                    SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                    emb = base_prep + timedelta(hours=random.randint(1, 4))
                    Bulto.objects.filter(pk=b.pk).update(fecha_embalaje=emb)
                    Solicitud.objects.filter(pk=s.pk).update(
                        fecha_en_despacho=base_prep,
                    )

                elif estado == 'en_despacho':
                    b = Bulto.objects.create(
                        solicitud=s,
                        transportista=transporte,
                        estado='pendiente',
                        creado_por=admin,
                        **_medidas_bulto(),
                    )
                    SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                    Solicitud.objects.filter(pk=s.pk).update(
                        fecha_en_despacho=base_prep,
                    )

                else:  # pendiente
                    b = Bulto.objects.create(
                        solicitud=s,
                        transportista=transporte,
                        estado='pendiente',
                        creado_por=admin,
                        **_medidas_bulto(),
                    )
                    SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)

                creadas += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Solicitudes activas demo creadas: {creadas} (últimos 1-3 días)'
            )
        )
