"""
Demo: borrar solicitudes operativas (opcional) y generar ~1 mes de pedidos de prueba
usando productos aleatorios de Stock en bodegas activas (core.Bodega activa=True).

NO borra usuarios, bodegas, configuración ni tablas de auth.
Requiere Stock con filas en esas bodegas, o usar --crear-stock-demo.

Con --reset-operativo se limpia todo lo que alimenta KPI/lead del dashboard
(solicitudes, detalles, bultos, transferencias y reservas). Las fechas del seed
alinean created_at y la línea de tiempo de bultos al día del pedido para que el
filtro por período (p. ej. 30 días) y los lead times sean coherentes.

Cada solicitud demo tiene al menos un bulto con peso y medidas (ficha y KPI).
Use --min-suc-calama para garantizar un mínimo de pedidos con cliente SUC CALAMA.

Uso:
  python manage.py seed_demo_mes --dry-run
  python manage.py seed_demo_mes --reset-operativo --confirm
  python manage.py seed_demo_mes --reset-operativo --confirm --crear-stock-demo --total 300 --dias 30 --min-suc-calama 50
"""

import random
from collections import Counter
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

# Pesos relativos en random.choices; SUC CALAMA priorizada para KPIs de sucursal.
CLIENTES_DEMO_PESOS = {
    'SUC CALAMA': 14,
    'SUC ANTOFAGASTA': 10,
    'SUC PTO MONTT': 10,
    'SUC LOS ANGELES': 10,
    'INTUB SPA': 6,
    'STARCO S.A.': 6,
    'PROS': 6,
    'COMERCIAL NORTE': 5,
    'MAIPU CONSTRUCTORA': 5,
    'AGRO SUR': 5,
    'TRANS IMPORT': 5,
}

ESTADOS_PESOS = [
    ('despachado', 0.38),
    ('en_despacho', 0.28),
    ('pendiente', 0.22),
    ('listo_despacho', 0.08),
    ('embalado', 0.04),
]

TRANSPORTES = ['PESCO', 'STARKEN', 'ESTAFETA', 'RETIRA_CLIENTE', 'VARMONTT']

# Debe coincidir con BODEGAS_DASHBOARD en core.views.calcular_indicadores_productividad
# (lead time por bodega en el dashboard).
BODEGAS_KPI_DASHBOARD = (
    '013-01', '013-03', '013-05', '013-08', '013-09', '013-PP', '013-PS',
)


def _elegir_estado():
    r = random.random()
    acum = 0.0
    for est, p in ESTADOS_PESOS:
        acum += p
        if r <= acum:
            return est
    return 'pendiente'


def _hora_random():
    return time(random.randint(8, 18), random.randint(0, 59), 0)


def _ts_pedido(dia, hora_solicitud, tz_chile):
    h = hora_solicitud or time(0, 0, 0)
    return tz_chile.localize(datetime.combine(dia, h))


def _cursor_prep_siguiente(prep_cursor):
    """Avanza el reloj de preparación; cada línea queda después de la anterior y del pedido."""
    return prep_cursor + timedelta(
        minutes=random.randint(8, 120),
        seconds=random.randint(0, 59),
    )


def _bodega_para_kpi(codigo_stock):
    c = (codigo_stock or '').strip()
    if c in BODEGAS_KPI_DASHBOARD:
        return c
    return random.choice(BODEGAS_KPI_DASHBOARD)


def _cliente_lista_para_seed(total, min_calama):
    """
    Lista de longitud `total` con al menos `min_calama` veces el cliente
    literal 'SUC CALAMA' (como espera el dashboard); el resto ponderado.
    """
    min_calama = min(total, max(0, min_calama))
    otros = [n for n in CLIENTES_DEMO_PESOS if n != 'SUC CALAMA']
    pesos_otros = [CLIENTES_DEMO_PESOS[n] for n in otros]
    out = ['SUC CALAMA'] * min_calama
    for _ in range(total - min_calama):
        out.append(random.choices(otros, weights=pesos_otros, k=1)[0])
    random.shuffle(out)
    return out


def _medidas_bulto_demo():
    """Largo/ancho/alto > 0 y peso para max(real, volumétrico) en el dashboard."""
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


def _pick_stock_rows(codigos_bodega, n_pool=500):
    """Filas (codigo, bodega, descripcion) con stock_disponible > 0."""
    qs = Stock.objects.filter(bodega__in=codigos_bodega).exclude(bodega='013')
    qs = qs.filter(stock_disponible__gt=0)
    rows = list(qs.values('codigo', 'bodega', 'descripcion')[:n_pool])
    return rows


def _crear_stock_demo(codigos_bodega, skus_por_bodega=15, cantidad=500):
    creados = 0
    for bod in codigos_bodega:
        if bod == '013':
            continue
        for i in range(skus_por_bodega):
            codigo = f'DEMO-{bod.replace("-", "")}-{i+1:03d}'
            _, created = Stock.objects.get_or_create(
                codigo=codigo,
                bodega=bod,
                defaults={
                    'descripcion': f'Producto demo {codigo}',
                    'bodega_nombre': bod,
                    'stock_disponible': cantidad,
                    'stock_reservado': 0,
                },
            )
            if created:
                creados += 1
    return creados


class Command(BaseCommand):
    help = 'Genera pedidos demo distribuidos en N días (bodegas activas + Stock).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--reset-operativo', action='store_true', help='Elimina solicitudes, bultos, transferencias y reservas')
        parser.add_argument('--confirm', action='store_true', help='Obligatorio con --reset-operativo')
        parser.add_argument('--dias', type=int, default=30)
        parser.add_argument('--total', type=int, default=150, help='Total de solicitudes a crear')
        parser.add_argument('--crear-stock-demo', action='store_true', help='Crea SKUs DEMO-* si falta stock útil')
        parser.add_argument('--skus-por-bodega', type=int, default=12)
        parser.add_argument('--min-lineas', type=int, default=1)
        parser.add_argument('--max-lineas', type=int, default=4)
        parser.add_argument(
            '--min-suc-calama',
            type=int,
            default=45,
            help='Mínimo de solicitudes con cliente exacto SUC CALAMA (acotado al --total)',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        reset = options['reset_operativo']
        confirm = options['confirm']
        dias = options['dias']
        total = options['total']
        min_suc_calama = options['min_suc_calama']
        crear_stock = options['crear_stock_demo']
        skus_bod = options['skus_por_bodega']
        min_l = options['min_lineas']
        max_l = options['max_lineas']

        if reset and not confirm:
            self.stdout.write(self.style.ERROR('Para borrar datos use también --confirm'))
            return

        bodegas_activas = list(Bodega.objects.filter(activa=True).values_list('codigo', flat=True))
        if not bodegas_activas:
            self.stdout.write(self.style.ERROR('No hay bodegas activas en core.Bodega'))
            return

        bodegas_sin_013 = [b for b in bodegas_activas if b != '013']
        pool = _pick_stock_rows(bodegas_sin_013)

        if len(pool) < 10 and crear_stock and not dry:
            n = _crear_stock_demo(bodegas_sin_013, skus_por_bodega=skus_bod)
            self.stdout.write(self.style.WARNING(f'Stock demo creado: {n} filas'))
            pool = _pick_stock_rows(bodegas_sin_013)
        elif len(pool) < 10:
            self.stdout.write(self.style.ERROR(
                'Pocas filas de Stock en bodegas activas (sin 013). '
                'Cargue inventario o ejecute con --crear-stock-demo'
            ))
            return

        if dry:
            self.stdout.write(f'[DRY] Bodegas activas: {bodegas_sin_013}')
            self.stdout.write(f'[DRY] Pool stock útil: {len(pool)} filas | pedidos a simular: {total} en {dias} días')
            self.stdout.write(f'[DRY] Mín. SUC CALAMA garantizados: {min(total, max(0, min_suc_calama))}')
            if reset:
                self.stdout.write('[DRY] Se borrarían solicitudes + dependencias operativas')
            return

        if reset:
            from bodega.models import BodegaTransferencia, StockReserva
            with transaction.atomic():
                n_sol = Solicitud.objects.count()
                BodegaTransferencia.objects.all().delete()
                StockReserva.objects.all().delete()
                Bulto.objects.all().delete()
                Solicitud.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Eliminadas {n_sol} solicitudes y datos operativos asociados en cascada.'))

        admin = User.objects.filter(rol='admin').first() or User.objects.filter(is_superuser=True).first()

        hoy = timezone.localdate()
        fecha_ini = hoy - timedelta(days=dias - 1)
        # reparte total pedidos en días al azar
        dias_list = list(range(dias))
        asignaciones = []
        for _ in range(total):
            asignaciones.append(random.choice(dias_list))
        por_dia = Counter(asignaciones)

        clientes_seq = _cliente_lista_para_seed(total, min_suc_calama)
        cli_i = 0

        chile = pytz.timezone('America/Santiago')
        seq_demo = 0
        creadas = 0

        for offset in range(dias):
            dia = fecha_ini + timedelta(days=offset)
            n_pedidos = por_dia.get(offset, 0)
            for _ in range(n_pedidos):
                seq_demo += 1
                estado = _elegir_estado()
                tipo = random.choices(['PC', 'OF', 'ST'], weights=[78, 14, 8], k=1)[0]
                cliente = clientes_seq[cli_i]
                cli_i += 1
                n_lineas = random.randint(min_l, max_l)

                lineas = []
                for _i in range(n_lineas):
                    row = random.choice(pool)
                    cant = random.randint(1, 8)
                    lineas.append({
                        'codigo': row['codigo'],
                        'bodega': row['bodega'],
                        'descripcion': (row.get('descripcion') or f"Item {row['codigo']}")[:500],
                        'cantidad': cant,
                    })

                primera = lineas[0]
                primera_bodega_kpi = _bodega_para_kpi(primera['bodega'])
                numero_pedido = ''
                if tipo != 'ST':
                    numero_pedido = f'DEMO-{dia.strftime("%Y%m%d")}-{seq_demo:04d}'

                with transaction.atomic():
                    guia = ''
                    num_ot = ''
                    if estado == 'despachado':
                        guia = str(random.randint(100000, 999999))
                        num_ot = str(random.randint(100000, 999999)) if random.random() > 0.35 else ''
                    elif estado in ('en_despacho', 'embalado', 'listo_despacho') and random.random() > 0.5:
                        num_ot = str(random.randint(100000, 999999))

                    hr_sol = _hora_random()
                    s = Solicitud(
                        tipo=tipo,
                        numero_pedido=numero_pedido,
                        cliente=cliente,
                        fecha_solicitud=dia,
                        hora_solicitud=hr_sol,
                        bodega=primera_bodega_kpi,
                        transporte=random.choice(TRANSPORTES),
                        estado=estado,
                        urgente=random.random() < 0.12,
                        codigo=primera['codigo'],
                        descripcion=primera['descripcion'],
                        cantidad_solicitada=sum(x['cantidad'] for x in lineas),
                        observacion='Pedido demo seed_demo_mes',
                        solicitante=admin,
                        afecta_stock=True,
                        numero_guia_despacho=guia,
                        numero_ot=num_ot,
                    )
                    s.save()
                    ts_sol = _ts_pedido(dia, hr_sol, chile)
                    Solicitud.objects.filter(pk=s.pk).update(created_at=ts_sol, updated_at=ts_sol)

                    eb = 'pendiente' if estado == 'pendiente' else 'preparado'
                    prep_cursor = ts_sol
                    for prod in lineas:
                        fp = None
                        if eb == 'preparado':
                            prep_cursor = _cursor_prep_siguiente(prep_cursor)
                            fp = prep_cursor
                        bod_kpi = _bodega_para_kpi(prod['bodega'])
                        SolicitudDetalle.objects.create(
                            solicitud=s,
                            codigo=prod['codigo'],
                            descripcion=prod['descripcion'],
                            cantidad=prod['cantidad'],
                            bodega=bod_kpi,
                            estado_bodega=eb,
                            preparado_por=admin if eb == 'preparado' else None,
                            fecha_preparacion=fp,
                        )

                    fechas_prep = [
                        d.fecha_preparacion
                        for d in s.detalles.all()
                        if d.fecha_preparacion
                    ]
                    base_prep = max(fechas_prep) if fechas_prep else ts_sol

                    if estado == 'despachado':
                        b = Bulto.objects.create(
                            solicitud=s,
                            transportista=s.transporte or 'PESCO',
                            estado='finalizado',
                            creado_por=admin,
                            **_medidas_bulto_demo(),
                        )
                        SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                        emb = base_prep + timedelta(hours=random.randint(2, 72))
                        env = emb + timedelta(hours=random.randint(1, 24))
                        ent = env + timedelta(hours=random.randint(1, 48))
                        Bulto.objects.filter(pk=b.pk).update(
                            fecha_embalaje=emb,
                            fecha_envio=env,
                            fecha_entrega=ent,
                        )
                    elif estado == 'listo_despacho':
                        b = Bulto.objects.create(
                            solicitud=s,
                            transportista=s.transporte or 'PESCO',
                            estado='listo_despacho',
                            creado_por=admin,
                            **_medidas_bulto_demo(),
                        )
                        SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                        emb = base_prep + timedelta(hours=random.randint(1, 36))
                        Bulto.objects.filter(pk=b.pk).update(fecha_embalaje=emb)
                    elif estado == 'embalado':
                        b = Bulto.objects.create(
                            solicitud=s,
                            transportista=s.transporte or 'PESCO',
                            estado='embalado',
                            creado_por=admin,
                            **_medidas_bulto_demo(),
                        )
                        SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                        emb = base_prep + timedelta(hours=random.randint(1, 24))
                        Bulto.objects.filter(pk=b.pk).update(fecha_embalaje=emb)
                    elif estado == 'en_despacho':
                        b = Bulto.objects.create(
                            solicitud=s,
                            transportista=s.transporte or 'PESCO',
                            estado='pendiente',
                            creado_por=admin,
                            **_medidas_bulto_demo(),
                        )
                        SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
                    elif estado == 'pendiente':
                        # Sin bulto la ficha de solicitud no muestra peso/medidas; KPI despachados no usa estos.
                        b = Bulto.objects.create(
                            solicitud=s,
                            transportista=s.transporte or 'PESCO',
                            estado='pendiente',
                            creado_por=admin,
                            **_medidas_bulto_demo(),
                        )
                        SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)

                creadas += 1

        n_calama = Solicitud.objects.filter(cliente='SUC CALAMA').count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Solicitudes demo creadas: {creadas} (últimos {dias} días) | cliente SUC CALAMA: {n_calama}'
            )
        )
