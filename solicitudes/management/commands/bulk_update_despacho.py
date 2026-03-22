"""
Comando para actualización masiva desde Excel (base bruta despacho).

Flujo completo (por defecto):
  1. Fase bodega: confirmar entregas (detalles→preparado, solicitudes→en_despacho)
  2. Fase despacho: actualizar estado, guía, crear bultos si faltan, finalizar

Uso: python manage.py bulk_update_despacho /ruta/al/archivo.xlsx
"""

import os
import warnings
warnings.filterwarnings('ignore', message='Parsing dates')

from django.core.management.base import BaseCommand

from solicitudes.bulk_update import (
    procesar_excel_bruto,
    ejecutar_completo,
    ejecutar_fase_bodega,
    ejecutar_actualizacion_masiva,
)


class Command(BaseCommand):
    help = 'Actualización masiva: 1) Confirmar entregas bodega 2) Actualizar despacho y bultos'

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo Excel (.xlsx)')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo previsualizar, no modificar la base de datos',
        )
        parser.add_argument(
            '--solo-despachados',
            action='store_true',
            help='Solo procesar filas marcadas ENTREGADO/DESPACHADO',
        )
        parser.add_argument(
            '--solo-fase-bodega',
            action='store_true',
            help='Solo ejecutar fase 1: confirmar entregas desde bodega',
        )

    def handle(self, *args, **options):
        ruta = options['archivo']
        dry_run = options['dry_run']
        solo_despachados = options['solo_despachados']
        solo_fase_bodega = options['solo_fase_bodega']

        if not os.path.exists(ruta):
            self.stdout.write(self.style.ERROR(f'Archivo no encontrado: {ruta}'))
            return

        with open(ruta, 'rb') as f:
            contenido = f.read()

        pedidos, errores = procesar_excel_bruto(contenido)
        if errores:
            for e in errores:
                self.stdout.write(self.style.ERROR(e))
            return

        if solo_despachados:
            from solicitudes.bulk_update import _normalizar_estado
            pedidos_filtrados = [p for p in pedidos if _normalizar_estado(p.get('estatus')) == 'despachado' or _normalizar_estado(p.get('status')) == 'despachado']
            self.stdout.write(f'Filtrado: {len(pedidos_filtrados)} pedidos con estatus despachado/entregado')

        self.stdout.write(f'Pedidos en Excel: {len(pedidos)}')

        if dry_run:
            from solicitudes.models import Solicitud
            encontrados = 0
            for ped in pedidos:
                numero, tipo, cliente = ped['numero'], ped.get('tipo', 'PC'), ped.get('cliente', '')
                fechas_posibles = ped.get('fechas_posibles') or []
                if ped.get('fecha'):
                    d = ped['fecha'].date() if hasattr(ped['fecha'], 'date') else ped['fecha']
                    if d and d not in fechas_posibles:
                        fechas_posibles = [d] + fechas_posibles

                base = Solicitud.objects.filter(tipo=tipo)
                base = base.filter(numero_st=numero) if tipo == 'ST' else base.filter(numero_pedido=numero)
                if cliente:
                    base = base.filter(cliente__icontains=cliente[:50])

                for f in fechas_posibles:
                    if base.filter(fecha_solicitud=f).exists():
                        encontrados += 1
                        break
                else:
                    if base.count() == 1:
                        encontrados += 1

            self.stdout.write(self.style.SUCCESS(f'[DRY-RUN] Encontrados: {encontrados}/{len(pedidos)}'))
            return

        if solo_fase_bodega:
            resultado = ejecutar_fase_bodega(contenido)
            self.stdout.write(self.style.SUCCESS(f'Detalles preparados: {resultado["detalles_preparados"]}'))
            self.stdout.write(self.style.SUCCESS(f'Solicitudes → en_despacho: {resultado["solicitudes_en_despacho"]}'))
        else:
            resultado = ejecutar_completo(contenido, solo_despachados=solo_despachados)
            dep = resultado.get('fase_despacho', {})
            self.stdout.write(self.style.SUCCESS(f'Fase bodega - Detalles preparados: {resultado.get("detalles_preparados", 0)}'))
            self.stdout.write(self.style.SUCCESS(f'Fase bodega - Solicitudes en_despacho: {resultado.get("solicitudes_en_despacho", 0)}'))
            self.stdout.write(self.style.SUCCESS(f'Fase despacho - Actualizados: {dep.get("actualizados", 0)}'))
            self.stdout.write(self.style.WARNING(f'No encontrados: {dep.get("total_no_encontrados", 0)}'))
            if dep.get('errores'):
                for e in dep['errores']:
                    self.stdout.write(self.style.ERROR(e))
