from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime
import hashlib
import json
import pytz

from solicitudes.models import Solicitud, SolicitudDetalle
from despacho.models import Bulto
from bodega.models import BodegaTransferencia
from configuracion.models import TipoSolicitud


@login_required
def informe_completo(request):
    """
    Vista para generar un informe completo tipo Excel con todos los datos de solicitudes,
    detalles, bodega, transferencias y despacho.
    
    Optimizado con caché y prefetch para evitar N+1 queries.
    """
    # Obtener parámetros de filtro (si los hay)
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    tipo_solicitud = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    
    # Crear clave de caché única basada en los filtros
    cache_key_data = {
        'fecha_desde': fecha_desde or 'all',
        'fecha_hasta': fecha_hasta or 'all',
        'tipo': tipo_solicitud or 'all',
        'estado': estado or 'all',
    }
    cache_key_str = json.dumps(cache_key_data, sort_keys=True)
    cache_key_hash = hashlib.md5(cache_key_str.encode()).hexdigest()
    cache_key = f'informe_completo_{cache_key_hash}'
    
    # Intentar obtener del caché (TTL: 10 minutos = 600 segundos)
    datos_cache = cache.get(cache_key)
    if datos_cache is not None:
        registros = datos_cache
        total_registros = len(registros)
    else:
        # Consulta optimizada con select_related y prefetch_related
        solicitudes_qs = Solicitud.objects.all().select_related('solicitante')
        
        # Aplicar filtros
        if fecha_desde:
            try:
                fecha_desde_dt = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                solicitudes_qs = solicitudes_qs.filter(fecha_solicitud__gte=fecha_desde_dt)
            except (ValueError, TypeError):
                pass
        
        if fecha_hasta:
            try:
                fecha_hasta_dt = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                solicitudes_qs = solicitudes_qs.filter(fecha_solicitud__lte=fecha_hasta_dt)
            except (ValueError, TypeError):
                pass
        
        if tipo_solicitud:
            solicitudes_qs = solicitudes_qs.filter(tipo=tipo_solicitud)
        
        if estado:
            solicitudes_qs = solicitudes_qs.filter(estado=estado)
        
        # Prefetch para detalles con bultos y transferencias (optimizado)
        detalles_prefetch = Prefetch(
            'detalles',
            queryset=SolicitudDetalle.objects.select_related(
                'bulto',
                'preparado_por'
            ).prefetch_related(
                Prefetch(
                    'transferencias',
                    queryset=BodegaTransferencia.objects.select_related(
                        'registrado_por'
                    ).order_by('-fecha_transferencia', '-hora_transferencia'),
                    to_attr='transferencias_list'
                )
            ).order_by('id'),
            to_attr='detalles_list'
        )
        
        # Prefetch para bultos
        bultos_prefetch = Prefetch(
            'bultos',
            queryset=Bulto.objects.all().order_by('-fecha_creacion'),
            to_attr='bultos_list'
        )
        
        # Ejecutar consulta con prefetches
        solicitudes = solicitudes_qs.prefetch_related(
            detalles_prefetch,
            bultos_prefetch
        ).order_by('-fecha_solicitud', '-hora_solicitud')
        
        # Construir lista de registros (uno por detalle)
        registros = []
        
        for solicitud in solicitudes:
            detalles = getattr(solicitud, 'detalles_list', [])
            bultos = getattr(solicitud, 'bultos_list', [])
            
            # Si no hay detalles, crear uno desde los datos de la cabecera (solicitudes antiguas)
            if not detalles:
                detalles = [{
                    'codigo': solicitud.codigo,
                    'descripcion': solicitud.descripcion,
                    'cantidad': solicitud.cantidad_solicitada,
                    'bodega': solicitud.bodega or '',
                    'estado_bodega': solicitud.estado,
                    'bulto': None,
                    'preparado_por': None,
                    'fecha_preparacion': None,
                    'transferencias_list': [],
                }]
            
            for detalle in detalles:
                # Determinar si detalle es un modelo Django o un diccionario
                es_modelo = hasattr(detalle, 'codigo') and hasattr(detalle, '_meta')
                
                # Obtener transferencias
                if es_modelo:
                    if hasattr(detalle, 'transferencias_list'):
                        transferencias = detalle.transferencias_list
                    elif hasattr(detalle, 'transferencias'):
                        transferencias = list(detalle.transferencias.all().order_by('-fecha_transferencia', '-hora_transferencia'))
                    else:
                        transferencias = []
                else:
                    # Es un diccionario
                    transferencias = detalle.get('transferencias_list', [])
                
                # Obtener transferencia SAP más reciente (puede no existir)
                transferencia_sap = transferencias[0] if transferencias else None
                
                # Obtener bulto asociado (puede ser None)
                if es_modelo:
                    bulto = detalle.bulto if hasattr(detalle, 'bulto') else None
                else:
                    bulto = detalle.get('bulto')
                
                # Si no hay bulto directo, buscar en la lista de bultos de la solicitud
                if not bulto and bultos:
                    # Intentar encontrar el bulto que contiene este detalle
                    for b in bultos:
                        if es_modelo and hasattr(detalle, 'id'):
                            if detalle in b.detalles.all():
                                bulto = b
                                break
                        else:
                            # Para diccionarios, no podemos hacer esta verificación
                            pass
                
                # Preparar datos del registro
                # Fechas y horas con formato seguro (convertir a zona horaria de Chile)
                chile_tz = pytz.timezone('America/Santiago')
                
                fecha_ingreso = ''
                hora_ingreso = ''
                if solicitud.fecha_solicitud:
                    fecha_ingreso = solicitud.fecha_solicitud.strftime('%d/%m/%Y')
                if solicitud.hora_solicitud:
                    # hora_solicitud es TimeField, ya está en hora local, solo formatear
                    hora_ingreso = solicitud.hora_solicitud.strftime('%H:%M')
                
                fecha_prep = ''
                hora_prep = ''
                if es_modelo:
                    if hasattr(detalle, 'fecha_preparacion') and detalle.fecha_preparacion:
                        # fecha_preparacion es DateTimeField, convertir a zona horaria de Chile
                        if timezone.is_aware(detalle.fecha_preparacion):
                            fecha_chile = detalle.fecha_preparacion.astimezone(chile_tz)
                        else:
                            fecha_chile = chile_tz.localize(detalle.fecha_preparacion)
                        fecha_prep = fecha_chile.strftime('%d/%m/%Y')
                        hora_prep = fecha_chile.strftime('%H:%M')
                else:
                    fecha_prep_obj = detalle.get('fecha_preparacion')
                    if fecha_prep_obj:
                        if hasattr(fecha_prep_obj, 'strftime'):
                            # Convertir a zona horaria de Chile si es datetime
                            if hasattr(fecha_prep_obj, 'astimezone'):
                                if timezone.is_aware(fecha_prep_obj):
                                    fecha_chile = fecha_prep_obj.astimezone(chile_tz)
                                else:
                                    fecha_chile = chile_tz.localize(fecha_prep_obj)
                                fecha_prep = fecha_chile.strftime('%d/%m/%Y')
                                hora_prep = fecha_chile.strftime('%H:%M')
                            else:
                                # Es un objeto time o date, formatear directo
                                fecha_prep = fecha_prep_obj.strftime('%d/%m/%Y') if hasattr(fecha_prep_obj, 'year') else ''
                                hora_prep = fecha_prep_obj.strftime('%H:%M') if hasattr(fecha_prep_obj, 'hour') else ''
                
                fecha_emb = ''
                hora_emb = ''
                fecha_desp = ''
                hora_desp = ''
                num_bulto = ''
                if bulto:
                    if hasattr(bulto, 'fecha_embalaje') and bulto.fecha_embalaje:
                        # fecha_embalaje es DateTimeField, convertir a zona horaria de Chile
                        if timezone.is_aware(bulto.fecha_embalaje):
                            fecha_chile = bulto.fecha_embalaje.astimezone(chile_tz)
                        else:
                            fecha_chile = chile_tz.localize(bulto.fecha_embalaje)
                        fecha_emb = fecha_chile.strftime('%d/%m/%Y')
                        hora_emb = fecha_chile.strftime('%H:%M')
                    
                    fecha_despacho_obj = (bulto.fecha_envio or bulto.fecha_entrega) if hasattr(bulto, 'fecha_envio') else None
                    if fecha_despacho_obj:
                        # Convertir a zona horaria de Chile
                        if timezone.is_aware(fecha_despacho_obj):
                            fecha_chile = fecha_despacho_obj.astimezone(chile_tz)
                        else:
                            fecha_chile = chile_tz.localize(fecha_despacho_obj)
                        fecha_desp = fecha_chile.strftime('%d/%m/%Y')
                        hora_desp = fecha_chile.strftime('%H:%M')
                    
                    num_bulto = bulto.codigo if hasattr(bulto, 'codigo') else ''
                
                # Obtener datos del detalle (modelo o diccionario)
                if es_modelo:
                    codigo = detalle.codigo
                    descripcion = detalle.descripcion or ''
                    cantidad = detalle.cantidad
                    bodega_asignada = detalle.bodega or ''
                    estado_linea = detalle.estado_bodega if hasattr(detalle, 'estado_bodega') else 'pendiente'
                    detalle_id = detalle.id
                else:
                    codigo = detalle.get('codigo', '')
                    descripcion = detalle.get('descripcion', '')
                    cantidad = detalle.get('cantidad', 0)
                    bodega_asignada = detalle.get('bodega', '')
                    estado_linea = detalle.get('estado_bodega', 'pendiente')
                    detalle_id = None
                
                registro = {
                    # Datos de Solicitud
                    'fecha_ingreso': fecha_ingreso,
                    'hora_ingreso': hora_ingreso,
                    'tipo': solicitud.get_tipo_display(),
                    'numero_pedido': solicitud.numero_pedido or '',
                    'cliente': solicitud.cliente or '',
                    'numero_guia': solicitud.numero_guia_despacho or '',
                    'transporte': solicitud.get_transporte_display() or solicitud.transporte or '',
                    'numero_ot': solicitud.numero_ot or '',
                    'estado_linea': estado_linea.replace('_', ' ').title() if estado_linea else 'Pendiente',
                    
                    # Datos de SolicitudDetalle
                    'codigo': codigo,
                    'descripcion': descripcion,
                    'cantidad': cantidad,
                    'bodega_asignada': bodega_asignada,
                    'fecha_preparacion': fecha_prep,
                    'hora_preparacion': hora_prep,
                    
                    # Datos de Transferencia SAP
                    'numero_transaccion_sap': transferencia_sap.numero_transferencia if transferencia_sap and hasattr(transferencia_sap, 'numero_transferencia') else '',
                    
                    # Datos de Bulto (pueden ser None)
                    'fecha_embalaje': fecha_emb,
                    'hora_embalaje': hora_emb,
                    'fecha_despacho': fecha_desp,
                    'hora_despacho': hora_desp,
                    'numero_bulto': num_bulto,
                    
                    # IDs para referencia (si aplica)
                    'solicitud_id': solicitud.id,
                    'detalle_id': detalle_id,
                }
                
                registros.append(registro)
        
        total_registros = len(registros)
        
        # Guardar en caché por 10 minutos
        cache.set(cache_key, registros, 600)
    
    # Obtener opciones para filtros
    tipos_activos = TipoSolicitud.activos()
    if tipos_activos.exists():
        tipos_disponibles = [(t.codigo, t.nombre) for t in tipos_activos]
    else:
        tipos_disponibles = Solicitud.TIPOS  # Fallback a choices hardcodeados
    estados_disponibles = Solicitud.objects.values_list('estado', flat=True).distinct().order_by('estado')
    
    context = {
        'registros': registros,
        'total_registros': total_registros,
        'tipos_disponibles': tipos_disponibles,
        'estados_disponibles': estados_disponibles,
        'filtros': {
            'fecha_desde': fecha_desde or '',
            'fecha_hasta': fecha_hasta or '',
            'tipo': tipo_solicitud or '',
            'estado': estado or '',
        }
    }
    
    return render(request, 'reportes/informe_completo.html', context)
