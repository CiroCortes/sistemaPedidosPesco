"""
Actualización masiva de solicitudes desde Excel (base bruta despacho).
Mapea columnas del archivo de la empresa y actualiza estado, guía, transporte, OT, etc.
"""

import pandas as pd
from io import BytesIO
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from django.utils import timezone

# Mapeo de columnas Excel (variaciones posibles)
COLUMNAS_EXCEL = {
    'fecha': ['fecha', 'Fecha'],
    'hr_pedido': ['Hr de Pedido', 'hr de pedido', 'hr de peddio'],
    'pc_of': ['PC / OF', 'pc', 'PC'],
    'numero': ['NUMERO', 'numero', 'Numero', 'nuemro'],
    'cliente': ['Cliente', 'cliente'],
    'cod_sap': ['COD SAP', 'cod sap', 'codigo'],
    'cantidad': ['CANTIDAD', 'cantidad', 'cant'],
    'bodega': ['BODEGA', 'bodega', 'cant bodega'],
    'estatus': ['ESTATUS', 'estatus', 'Estatus'],
    'status': ['STATUS', 'status'],
    'fecha_entrega': ['Fecha de entrega', 'fecha de entrega'],
    'hr_entrega': ['Hr de Entrega', 'hr de entrega', 'hora de entrega'],
    'guia': ['N° Guia', 'N° Guía', 'guia transporte', 'Guia', 'guiam transporte'],
    'transporte': ['Transporte', 'transporte', 'tranferencia'],
    'ot': ['OT', 'ot', 'ot mdidas', 'ot medidas'],
    'peso': ['Peso', 'peso'],
    'fecha_embalado': ['FECHA EMBALADO', 'fecha embalado', 'fecha ebalado'],
    'fecha_despacho': ['Fecha despacho', 'fecha despacho'],
}


def _find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    """Encuentra la columna que coincida con alguno de los alias."""
    cols = [c.strip() for c in df.columns]
    for alias in aliases:
        for c in cols:
            if alias.lower() in c.lower() or c.lower() in alias.lower():
                return c
    return None


def _normalizar_estado(estatus: Any) -> Optional[str]:
    """Mapea ESTATUS del Excel a estado del sistema."""
    if estatus is None or (isinstance(estatus, float) and pd.isna(estatus)):
        return None
    s = str(estatus).strip().upper()
    # Estados que indican despachado/entregado
    despachado_variantes = [
        'ENTREGADO', 'DESPACHADO', 'RETIRADO', 'ENTREGADO ', 'ENTEGADO',
        'ENTRGADO', 'EBTREGADO', 'entregado', 'ENTREGA', 'ENTREGA '
    ]
    for v in despachado_variantes:
        if v in s or s in v:
            return 'despachado'
    # Pendiente / en proceso
    if 'PENDIENTE' in s or 'EN DESPACHO' in s:
        return 'en_despacho'
    if 'EMBALADO' in s or 'LISTO' in s:
        return 'listo_despacho'
    return None


def _normalizar_tipo(pc_of: Any) -> Optional[str]:
    """
    Mapea 'PC / OF' del Excel al tipo del sistema.
    PC y OF pueden compartir el mismo número; el tipo los distingue.
    """
    if pc_of is None or (isinstance(pc_of, float) and pd.isna(pc_of)):
        return None
    t = str(pc_of).strip().upper()
    # Valores válidos del sistema: PC, OC, EM, ST, OF, RM
    mapa = {
        'PC': 'PC', 'PC ': 'PC', 'Pc': 'PC', 'pC': 'PC', 'pc': 'PC',
        'OF': 'OF', 'OF ': 'OF', 'oF': 'OF', 'Of': 'OF', 'of': 'OF', 'oc': 'OC',
        'OC': 'OC', 'OC ': 'OC',
        'ST': 'ST', 'st': 'ST',
        'EM': 'EM', 'RM': 'RM', 'rm': 'RM',
        'TF': 'ST',  # Transferencia -> ST
        'PE': 'PC',  # PE posiblemente pedido -> PC
    }
    return mapa.get(t) or (t if t in ('PC', 'OC', 'EM', 'ST', 'OF', 'RM') else None)


def _normalizar_transporte(transporte: Any) -> Optional[str]:
    """Mapea Transporte del Excel a slug del sistema."""
    if transporte is None or (isinstance(transporte, float) and pd.isna(transporte)):
        return None
    t = str(transporte).strip().upper()
    mapa = {
        'CAMION PESCO': 'PESCO',
        'CAMION PESCO ': 'PESCO',
        'PESCO': 'PESCO',
        'STARKEN': 'STARKEN',
        'STARKEN ': 'STARKEN',
        'ESTAFETA': 'ESTAFETA',
        'RETIRA CLIENTE': 'RETIRA_CLIENTE',
        'VARMONTT': 'VARMONTT',
        'KAIZEN': 'KAIZEN',
        'KAIZEN ': 'KAIZEN',
        'AV LOGISTICA': 'OTRO',
        'GEOMAIL': 'OTRO',
        'EXPORTACION': 'OTRO',
    }
    for k, v in mapa.items():
        if k in t or t == k:
            return v
    return 'OTRO' if t else None


def _to_date(val) -> Optional[datetime]:
    """Convierte valor a fecha."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()
    try:
        return pd.to_datetime(val, dayfirst=True).to_pydatetime()
    except Exception:
        return None


def _fechas_posibles(fecha_val) -> List:
    """
    Retorna lista de fechas posibles por ambigüedad DD/MM vs MM/DD.
    Excel 2/12 puede ser 2-dic (Chile) o 12-feb (US). Probamos ambas.
    """
    fechas = []
    if fecha_val is None or (isinstance(fecha_val, float) and pd.isna(fecha_val)):
        return fechas
    for dayfirst in (True, False):
        try:
            d = pd.to_datetime(fecha_val, dayfirst=dayfirst).date()
            if d not in fechas:
                fechas.append(d)
        except Exception:
            pass
    return fechas


def procesar_excel_bruto(archivo_bytes: bytes) -> Tuple[List[Dict], List[str]]:
    """
    Lee el Excel y agrupa por pedido (numero + fecha + cliente).
    Retorna lista de diccionarios con datos a actualizar y lista de errores.
    """
    try:
        df = pd.read_excel(BytesIO(archivo_bytes))
    except Exception as e:
        return [], [f'Error al leer Excel: {str(e)}']

    errores = []
    col_map = {}

    for key, aliases in COLUMNAS_EXCEL.items():
        c = _find_column(df, aliases)
        if c:
            col_map[key] = c

    if 'numero' not in col_map or 'fecha' not in col_map:
        return [], ['Faltan columnas obligatorias: NUMERO y fecha']

    # Agrupar por (numero, fecha, cliente, tipo)
    # tipo es crítico: PC y OF pueden tener el mismo número
    def _valor(row, key, default=''):
        if key not in col_map:
            return default
        val = row.get(col_map[key])
        if pd.isna(val):
            return default
        return str(val).strip() if val else default

    def _valor_num(row, key):
        if key not in col_map:
            return None
        val = row.get(col_map[key])
        if pd.isna(val):
            return None
        try:
            return str(int(float(val))) if val else None
        except (ValueError, TypeError):
            return str(val).strip() if val else None

    # Agrupar filas por pedido
    pedidos = {}
    for idx, row in df.iterrows():
        numero = _valor_num(row, 'numero')
        if not numero:
            continue
        fecha_val = row.get(col_map.get('fecha'))
        fecha_dt = _to_date(fecha_val)
        fecha_str = fecha_dt.strftime('%Y-%m-%d') if fecha_dt else ''
        cliente = _valor(row, 'cliente')
        tipo_raw = _valor(row, 'pc_of')
        tipo = _normalizar_tipo(tipo_raw) or 'PC'  # fallback
        key = (numero, fecha_str, cliente[:100] if cliente else '', tipo)
        fecha_raw = row.get(col_map.get('fecha')) if col_map.get('fecha') else None
        fechas_posibles = _fechas_posibles(fecha_raw)

        if key not in pedidos:
            pedidos[key] = {
                'numero': numero,
                'tipo': tipo,
                'fecha': fecha_dt,
                'fecha_str': fecha_str,
                'fechas_posibles': fechas_posibles,
                'cliente': cliente,
                'estatus': _valor(row, 'estatus'),
                'status': _valor(row, 'status'),
                'guia': _valor_num(row, 'guia') or _valor(row, 'guia'),
                'transporte': _valor(row, 'transporte'),
                'ot': _valor_num(row, 'ot') or _valor(row, 'ot'),
                'filas': []
            }
        row_data = {
            'cod_sap': _valor(row, 'cod_sap'),
            'cantidad': _valor_num(row, 'cantidad') or 0,
            'bodega': _valor(row, 'bodega') or '',
        }
        pedidos[key]['filas'].append(row_data)
        # Tomar el estatus más "avanzado" de ESTATUS o STATUS
        est = _valor(row, 'estatus')
        st = _valor(row, 'status') if 'status' in col_map else ''
        if est:
            pedidos[key]['estatus'] = est
        if st:
            pedidos[key]['status'] = st
        # Si STATUS indica despachado, priorizar
        if _normalizar_estado(st) == 'despachado':
            pedidos[key]['estatus'] = st
        if _valor_num(row, 'guia'):
            pedidos[key]['guia'] = _valor_num(row, 'guia') or pedidos[key]['guia']
        if _valor(row, 'transporte'):
            pedidos[key]['transporte'] = _valor(row, 'transporte') or pedidos[key]['transporte']
        if _valor_num(row, 'ot'):
            pedidos[key]['ot'] = _valor_num(row, 'ot') or pedidos[key]['ot']

    return list(pedidos.values()), errores


def _crear_bulto_si_falta(solicitud, transporte: str = 'PESCO') -> bool:
    """
    Si la solicitud no tiene bultos, crea uno y asigna todos los detalles.
    Retorna True si se creó.
    """
    from despacho.models import Bulto

    if Bulto.objects.filter(solicitud=solicitud).exists():
        return False
    bulto = Bulto.objects.create(
        solicitud=solicitud,
        transportista=transporte,
        estado='listo_despacho',
        creado_por=None,
    )
    solicitud.detalles.all().update(bulto=bulto)
    return True


def _aplicar_despacho_completo(solicitud, transporte: str = 'PESCO') -> bool:
    """
    Aplica la lógica completa de despacho: crear bulto si falta, finalizar bultos, descontar stock.
    Retorna True si se procesó correctamente.
    """
    from despacho.models import Bulto
    from solicitudes.services import descontar_stock_despachado

    if solicitud.estado != 'despachado':
        return False
    _crear_bulto_si_falta(solicitud, transporte)
    bultos = Bulto.objects.filter(solicitud=solicitud)
    ahora = timezone.now()
    for bulto in bultos:
        bulto.estado = 'finalizado'
        if not bulto.fecha_entrega:
            bulto.fecha_entrega = ahora
        if not bulto.fecha_envio:
            bulto.fecha_envio = ahora
        bulto.save(update_fields=['estado', 'fecha_entrega', 'fecha_envio'])
    solicitud.detalles.filter(bulto__isnull=False).exclude(estado_bodega='preparado').update(estado_bodega='preparado')
    descontar_stock_despachado(solicitud)
    return True


def _normalizar_bodega(val: Any) -> str:
    """Normaliza código de bodega: 13 -> 013, 013-01 se mantiene."""
    if not val:
        return ''
    s = str(val).strip()
    if s.isdigit() and len(s) <= 2:
        return s.zfill(3)
    return s


def ejecutar_fase_bodega(archivo_bytes: bytes) -> Dict[str, Any]:
    """
    Fase 1: Confirmar entregas desde bodega.
    Para cada fila del Excel que indique entregado: marca detalle como preparado, mueve stock,
    y si todos los detalles están preparados, solicitud pasa a en_despacho.
    """
    from django.db import transaction
    from solicitudes.models import Solicitud, SolicitudDetalle
    from bodega.views import mover_stock, resolver_bodega_origen
    from bodega.models import BodegaTransferencia

    pedidos, errores = procesar_excel_bruto(archivo_bytes)
    if errores:
        return {'confirmados': 0, 'detalles_preparados': 0, 'solicitudes_en_despacho': 0, 'errores': errores}

    detalles_preparados = 0
    solicitudes_pasadas = set()

    for ped in pedidos:
        if not (_normalizar_estado(ped.get('estatus')) == 'despachado' or _normalizar_estado(ped.get('status')) == 'despachado'):
            continue
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

        solicitud = None
        for f in fechas_posibles:
            q = base.filter(fecha_solicitud=f)
            if q.exists():
                solicitud = q.first()
                break
        if not solicitud and base.count() == 1:
            solicitud = base.first()
        if not solicitud:
            continue

        for fila in ped.get('filas', []):
            cod_sap = (fila.get('cod_sap') or '').strip()
            cantidad = fila.get('cantidad') or 0
            bodega_excel = _normalizar_bodega(fila.get('bodega'))

            if not cod_sap:
                continue
            qs = SolicitudDetalle.objects.filter(solicitud=solicitud, codigo=cod_sap)
            if cantidad:
                try:
                    qs = qs.filter(cantidad=int(cantidad))
                except (ValueError, TypeError):
                    pass
            detalle = qs.exclude(estado_bodega='preparado').exclude(bodega='013').first()

            if detalle and detalle.estado_bodega != 'preparado':
                bodega_origen = bodega_excel or resolver_bodega_origen(detalle, None)
                if not bodega_origen and detalle.bodega:
                    bodega_origen = detalle.bodega

                with transaction.atomic():
                    detalle.estado_bodega = 'preparado'
                    detalle.preparado_por = None
                    detalle.fecha_preparacion = timezone.now()
                    if bodega_origen:
                        detalle.bodega = bodega_origen
                    detalle.save(update_fields=['estado_bodega', 'preparado_por', 'fecha_preparacion', 'bodega'])
                    mover_stock(detalle.codigo, bodega_origen, detalle.cantidad, solicitud=detalle.solicitud)
                    detalles_preparados += 1

                solicitud.refresh_from_db()
                pendientes = solicitud.detalles.exclude(bodega='013').exclude(estado_bodega='preparado')
                if not pendientes.exists():
                    solicitud.estado = 'en_despacho'
                    solicitud.save(update_fields=['estado'])
                    solicitudes_pasadas.add(solicitud.id)

    return {
        'detalles_preparados': detalles_preparados,
        'solicitudes_en_despacho': len(solicitudes_pasadas),
        'errores': errores,
    }


def ejecutar_actualizacion_masiva(archivo_bytes: bytes, solo_despachados: bool = False) -> Dict[str, Any]:
    """
    Procesa el Excel y actualiza las solicitudes coincidentes.
    Si el estado pasa a despachado, aplica flujo completo (bultos, stock).
    solo_despachados: si True, solo procesa filas con ESTATUS/STATUS = ENTREGADO/DESPACHADO.
    Retorna { actualizados: int, no_encontrados: [], errores: [] }
    """
    from solicitudes.models import Solicitud

    pedidos, errores = procesar_excel_bruto(archivo_bytes)
    if solo_despachados:
        pedidos = [p for p in pedidos if _normalizar_estado(p.get('estatus')) == 'despachado' or _normalizar_estado(p.get('status')) == 'despachado']
    if errores:
        return {'actualizados': 0, 'no_encontrados': [], 'errores': errores}

    actualizados = 0
    no_encontrados = []

    for ped in pedidos:
        numero = ped['numero']
        tipo = ped.get('tipo', 'PC')
        cliente = ped['cliente']
        fechas_posibles = ped.get('fechas_posibles') or []
        if ped.get('fecha'):
            fecha_dt = ped['fecha']
            d = fecha_dt.date() if hasattr(fecha_dt, 'date') else fecha_dt
            if d and d not in fechas_posibles:
                fechas_posibles = [d] + fechas_posibles

        # Buscar solicitud: numero + tipo + cliente
        # Fecha: probar fechas_posibles (2/12 vs 12/2) y luego sin fecha si no hay match
        base = Solicitud.objects.filter(tipo=tipo)
        if tipo == 'ST':
            base = base.filter(numero_st=numero)
        else:
            base = base.filter(numero_pedido=numero)
        if cliente:
            base = base.filter(cliente__icontains=cliente[:50])

        solicitud = None
        for f in fechas_posibles:
            q = base.filter(fecha_solicitud=f)
            if q.exists():
                solicitud = q.first()
                break
        if not solicitud and base.exists():
            # Fallback: mismo numero+tipo+cliente, cualquier fecha (único candidato)
            if base.count() == 1:
                solicitud = base.first()
        if not solicitud:
            no_encontrados.append({
                'numero': numero,
                'tipo': tipo,
                'fecha': ped['fecha_str'],
                'cliente': cliente[:50] if cliente else '-'
            })
            continue

        # Estatus: considerar ESTATUS y STATUS (la planilla usa ambas)
        estatus_val = _normalizar_estado(ped.get('estatus'))
        status_val = _normalizar_estado(ped.get('status'))
        nuevo_estado = estatus_val or status_val

        # Aplicar actualizaciones
        cambiado = False
        if nuevo_estado and solicitud.estado != nuevo_estado:
            solicitud.estado = nuevo_estado
            cambiado = True

        guia = ped.get('guia')
        if guia and solicitud.numero_guia_despacho != str(guia):
            solicitud.numero_guia_despacho = str(guia)[:100]
            cambiado = True

        transporte = _normalizar_transporte(ped.get('transporte'))
        if transporte and solicitud.transporte != transporte:
            solicitud.transporte = transporte
            cambiado = True

        ot = ped.get('ot')
        if ot and str(solicitud.numero_ot) != str(ot):
            solicitud.numero_ot = str(ot)[:100]
            cambiado = True

        if cambiado:
            solicitud.save()
            if nuevo_estado == 'despachado':
                try:
                    transp = _normalizar_transporte(ped.get('transporte')) or 'PESCO'
                    _aplicar_despacho_completo(solicitud, transporte=transp)
                except Exception:
                    pass  # Log but don't fail the batch
            actualizados += 1

    return {
        'actualizados': actualizados,
        'no_encontrados': no_encontrados[:50],
        'total_no_encontrados': len(no_encontrados),
        'errores': errores,
        'total_procesados': len(pedidos)
    }


def ejecutar_completo(archivo_bytes: bytes, solo_despachados: bool = False) -> Dict[str, Any]:
    """
    Ejecuta el flujo completo en orden:
    1. Fase bodega: confirmar entregas (detalles preparado, solicitud en_despacho)
    2. Fase despacho: actualizar estado, guía, bultos (crear si falta), finalizar
    """
    resultado_bodega = ejecutar_fase_bodega(archivo_bytes)
    resultado_despacho = ejecutar_actualizacion_masiva(archivo_bytes, solo_despachados=solo_despachados)
    return {
        'fase_bodega': resultado_bodega,
        'fase_despacho': resultado_despacho,
        'detalles_preparados': resultado_bodega.get('detalles_preparados', 0),
        'solicitudes_en_despacho': resultado_bodega.get('solicitudes_en_despacho', 0),
        'actualizados': resultado_despacho.get('actualizados', 0),
    }
