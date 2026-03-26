"""
Sin borrar solicitudes existentes:

1) Rellena peso y medidas en bultos de solicitudes en listo_despacho que ya tienen
   bultos pero dimensiones en cero (torta de kilos / ficha despacho).

2) Crea N solicitudes nuevas con cliente SUC CALAMA y estado aleatorio en
   pendiente | en_despacho | despachado (líneas, fechas y bultos alineados con seed_demo_mes).

Uso:
  python manage.py enriquecer_listos_y_calama --dry-run
  python manage.py enriquecer_listos_y_calama --cantidad-calama 45
  python manage.py enriquecer_listos_y_calama --solo-medidas-listos
  python manage.py enriquecer_listos_y_calama --solo-calama --crear-stock-demo
"""

import random
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q, Max
from django.utils import timezone

import pytz

from core.models import Bodega
from despacho.models import Bulto
from solicitudes.models import Solicitud, SolicitudDetalle

from solicitudes.management.commands.seed_demo_mes import (
    TRANSPORTES,
    _bodega_para_kpi,
    _crear_stock_demo,
    _cursor_prep_siguiente,
    _hora_random,
    _medidas_bulto_demo,
    _pick_stock_rows,
    _ts_pedido,
)

User = get_user_model()

ESTADOS_CALAMA = ('pendiente', 'en_despacho', 'despachado')


def _crear_una_solicitud_calama(
    *,
    admin,
    pool,
    chile,
    dia,
    estado,
    seq_key,
    min_l,
    max_l,
):
    """Una solicitud completa (detalles + bulto/s según estado), cliente SUC CALAMA."""
    cliente = 'SUC CALAMA'
    tipo = random.choices(['PC', 'OF', 'ST'], weights=[78, 14, 8], k=1)[0]
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
        numero_pedido = f'DEMO-CALAMA-{dia.strftime("%Y%m%d")}-{seq_key:05d}'

    with transaction.atomic():
        guia = ''
        num_ot = ''
        if estado == 'despachado':
            guia = str(random.randint(100000, 999999))
            num_ot = str(random.randint(100000, 999999)) if random.random() < 0.35 else ''
        elif estado == 'en_despacho' and random.random() > 0.5:
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
            observacion='Pedido demo enriquecer_listos_y_calama (SUC CALAMA)',
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
            emb = base_prep + timedelta(hours=random.randint(2, 48))
            env = emb + timedelta(hours=random.randint(1, 18))
            ent = env + timedelta(hours=random.randint(1, 36))
            Bulto.objects.filter(pk=b.pk).update(
                fecha_embalaje=emb,
                fecha_envio=env,
                fecha_entrega=ent,
            )
        elif estado == 'en_despacho':
            b = Bulto.objects.create(
                solicitud=s,
                transportista=s.transporte or 'PESCO',
                estado='pendiente',
                creado_por=admin,
                **_medidas_bulto_demo(),
            )
            SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)
        else:
            b = Bulto.objects.create(
                solicitud=s,
                transportista=s.transporte or 'PESCO',
                estado='pendiente',
                creado_por=admin,
                **_medidas_bulto_demo(),
            )
            SolicitudDetalle.objects.filter(solicitud=s).update(bulto=b)

    return s


class Command(BaseCommand):
    help = 'Rellena medidas en bultos listo_despacho y crea solicitudes SUC CALAMA sin reset global.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--solo-medidas-listos', action='store_true', help='Solo paso 1 (bultos listo_despacho)')
        parser.add_argument('--solo-calama', action='store_true', help='Solo paso 2 (solicitudes nuevas)')
        parser.add_argument('--cantidad-calama', type=int, default=45)
        parser.add_argument('--dias-ventana', type=int, default=30, help='Días hacia atrás para fechar pedidos Calama')
        parser.add_argument('--min-lineas', type=int, default=1)
        parser.add_argument('--max-lineas', type=int, default=4)
        parser.add_argument('--crear-stock-demo', action='store_true')

    def handle(self, *args, **options):
        dry = options['dry_run']
        solo_med = options['solo_medidas_listos']
        solo_cal = options['solo_calama']
        n_calama = max(0, options['cantidad_calama'])
        dias_win = max(1, options['dias_ventana'])
        min_l = options['min_lineas']
        max_l = options['max_lineas']
        crear_stock = options['crear_stock_demo']

        do_medidas = not solo_cal
        do_calama = not solo_med

        if solo_med and solo_cal:
            self.stderr.write(self.style.ERROR('No use --solo-medidas-listos y --solo-calama a la vez.'))
            return

        hoy = timezone.localdate()
        chile = pytz.timezone('America/Santiago')

        if do_medidas:
            qs_b = Bulto.objects.filter(solicitud__estado='listo_despacho').filter(
                Q(largo_cm__lte=0) | Q(ancho_cm__lte=0) | Q(alto_cm__lte=0)
            )
            n_b = qs_b.count()
            self.stdout.write(f'Bultos listo_despacho sin medidas útiles: {n_b}')
            if dry:
                self.stdout.write('[DRY] No se actualizaron bultos.')
            elif n_b:
                actual = 0
                for b in qs_b.iterator(chunk_size=100):
                    Bulto.objects.filter(pk=b.pk).update(**_medidas_bulto_demo())
                    actual += 1
                self.stdout.write(self.style.SUCCESS(f'Medidas asignadas a {actual} bultos (listo_despacho).'))

        if do_calama:
            if n_calama == 0:
                self.stdout.write('Paso Calama: cantidad 0, omitido.')
            else:
                admin = User.objects.filter(rol='admin').first() or User.objects.filter(is_superuser=True).first()
                if not admin:
                    self.stderr.write(self.style.ERROR('Se necesita un usuario admin o superuser como solicitante.'))
                    return

                bodegas_activas = list(Bodega.objects.filter(activa=True).values_list('codigo', flat=True))
                bodegas_sin_013 = [b for b in bodegas_activas if b != '013']
                pool = _pick_stock_rows(bodegas_sin_013)

                skus_bod = 12
                if len(pool) < 10 and crear_stock and not dry:
                    n = _crear_stock_demo(bodegas_sin_013, skus_por_bodega=skus_bod)
                    self.stdout.write(self.style.WARNING(f'Stock demo creado: {n} filas'))
                    pool = _pick_stock_rows(bodegas_sin_013)
                elif len(pool) < 10:
                    self.stderr.write(self.style.ERROR(
                        'Pocas filas de Stock. Cargue inventario o use --crear-stock-demo'
                    ))
                    return

                id_base = Solicitud.objects.aggregate(m=Max('id'))['m'] or 0
                if dry:
                    self.stdout.write(
                        f'[DRY] Se crearían {n_calama} solicitudes SUC CALAMA '
                        f'(estados {ESTADOS_CALAMA}) en ventana {dias_win} días.'
                    )
                else:
                    creadas = 0
                    for i in range(n_calama):
                        dia = hoy - timedelta(days=random.randint(0, dias_win - 1))
                        estado = random.choice(ESTADOS_CALAMA)
                        seq_key = id_base + i + 1
                        _crear_una_solicitud_calama(
                            admin=admin,
                            pool=pool,
                            chile=chile,
                            dia=dia,
                            estado=estado,
                            seq_key=seq_key,
                            min_l=min_l,
                            max_l=max_l,
                        )
                        creadas += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'SUC CALAMA: {creadas} solicitudes nuevas (pendiente/en_despacho/despachado aleatorio).'
                        )
                    )
