"""
Vistas principales del Sistema PESCO
Basado en la arquitectura de sistemaGDV
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Avg, Min, Max, Sum, F, ExpressionWrapper, DurationField, OuterRef, Subquery, Case, When, DecimalField
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, datetime, date, time as dt_time
from decimal import Decimal
import json
import zoneinfo
from despacho.models import Bulto
from bodega.models import Stock
from solicitudes.models import Solicitud, SolicitudDetalle
from .models import Usuario
from configuracion.models import TransporteConfig

_CHILE_TZ = zoneinfo.ZoneInfo('America/Santiago')


def _es_transporte_retira_cliente(transporte_raw):
    """True si el transporte de la solicitud es retiro en sucursal / Retira cliente (código RETIRA_CLIENTE)."""
    t = (transporte_raw or '').strip().upper().replace(' ', '_')
    return t == 'RETIRA_CLIENTE'


def inicio_efectivo_lead_time(solicitud):
    """
    Inicio del reloj para lead time: max(fecha/hora negocio del pedido, created_at).
    Evita inflar horas cuando fecha_solicitud y created_at no están alineados (cargas tardías,
    Excel retroactivo o cierres masivos).
    """
    if not solicitud.fecha_solicitud:
        return solicitud.created_at
    hr = solicitud.hora_solicitud or dt_time(0, 0, 0)
    inicio_negocio = datetime.combine(solicitud.fecha_solicitud, hr, tzinfo=_CHILE_TZ)
    creado = solicitud.created_at
    if creado is None:
        return inicio_negocio
    if timezone.is_naive(creado):
        creado = timezone.make_aware(creado, _CHILE_TZ)
    return max(inicio_negocio, creado)


def _lead_horas_validas(delta_horas):
    """Excluye solo deltas negativos (fechas incoherentes)."""
    return delta_horas >= 0


def calcular_horas_laborales(fecha_inicio, fecha_fin):
    """
    Calcula las horas laborales entre dos fechas.
    Considera solo días hábiles (lunes a viernes) y 8 horas por día.
    
    Args:
        fecha_inicio: datetime - Fecha de inicio
        fecha_fin: datetime - Fecha de fin
        
    Returns:
        float: Total de horas laborales
    """
    if not fecha_inicio or not fecha_fin:
        return 0
    
    # Asegurar que trabajamos con fechas aware en la zona horaria local
    if timezone.is_aware(fecha_inicio):
        fecha_inicio = timezone.localtime(fecha_inicio)
    if timezone.is_aware(fecha_fin):
        fecha_fin = timezone.localtime(fecha_fin)
    
    # Si fecha_fin es menor que fecha_inicio, retornar 0
    if fecha_fin < fecha_inicio:
        return 0
    
    total_horas = 0
    fecha_actual = fecha_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_limite = fecha_fin.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    while fecha_actual <= fecha_limite:
        # Solo contar días laborales (lunes=0 a viernes=4)
        if fecha_actual.weekday() < 5:  # 0-4 = lunes a viernes
            # Si es el primer día
            if fecha_actual.date() == fecha_inicio.date():
                # Calcular desde la hora de inicio hasta el fin del día (máx 8 horas)
                hora_inicio = fecha_inicio.hour + fecha_inicio.minute / 60 + fecha_inicio.second / 3600
                # Si termina el mismo día
                if fecha_actual.date() == fecha_fin.date():
                    hora_fin = fecha_fin.hour + fecha_fin.minute / 60 + fecha_fin.second / 3600
                    total_horas += min(8, hora_fin - hora_inicio)
                else:
                    # Contar desde hora_inicio hasta fin de jornada (8 horas max desde inicio del día laboral)
                    total_horas += min(8, 24 - hora_inicio)
            # Si es el último día (pero no el primero)
            elif fecha_actual.date() == fecha_fin.date():
                hora_fin = fecha_fin.hour + fecha_fin.minute / 60 + fecha_fin.second / 3600
                total_horas += min(8, hora_fin)
            # Días intermedios: 8 horas laborales
            else:
                total_horas += 8
        
        # Avanzar al siguiente día
        fecha_actual += timedelta(days=1)
    
    return total_horas


def login_view(request):
    """
    Vista de login
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenido {user.nombre_completo}')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')


def logout_view(request):
    """
    Vista de logout
    """
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente')
    return redirect('login')


@login_required
def dashboard(request):
    """
    Dashboard principal
    Muestra diferentes métricas según el rol del usuario
    """
    user = request.user
    
    # Obtener fecha actual en zona horaria de Chile
    fecha_chile = timezone.localtime(timezone.now())
    
    # Obtener parámetros de filtro
    periodo = request.GET.get('periodo', '30')  # Default: últimos 30 días
    try:
        periodo_dias = int(periodo)
    except (ValueError, TypeError):
        periodo_dias = 30
    
    transporte_filtro = request.GET.get('transporte', None)
    if transporte_filtro == '':
        transporte_filtro = None

    # Valores por defecto: el template usa `user.es_admin and indicadores` en varios sitios
    # y Django evalúa ambos operandos sin cortocircuito; si faltan, falla para bodega/despacho.
    context = {
        'user': user,
        'hoy': fecha_chile.date(),
        'indicadores': None,
        'periodo_actual': periodo_dias,
        'transporte_filtro': transporte_filtro,
    }
    
    if user.es_admin():
        # Admin ve todo - Optimizado: 1 query en lugar de 6
        stats = Solicitud.objects.aggregate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(estado='pendiente')),
            en_despacho=Count('id', filter=Q(estado='en_despacho')),
            listo_despacho=Count('id', filter=Q(estado='listo_despacho')),
            # embaladas: omitido de KPI; listo_despacho ya refleja pedido embalado/listo. Reactivar ambas líneas abajo si se quiere tarjeta propia.
            # embaladas=Count('id', filter=Q(estado='embalado')),
            despachadas=Count('id', filter=Q(estado='despachado')),
            urgentes=Count('id', filter=Q(
                urgente=True,
                estado='pendiente'
            ))
        )
        
        # Calcular indicadores de productividad
        try:
            indicadores = calcular_indicadores_productividad(
                periodo_dias=periodo_dias,
                transporte_filtro=transporte_filtro
            )
        except Exception as e:
            # Si hay error, usar valores por defecto para no bloquear el dashboard
            import traceback
            print(f"Error al calcular indicadores: {e}")
            traceback.print_exc()
            indicadores = {
                'lt_prep_promedio': 0,
                'lt_emb_promedio': 0,
                'lt_total_promedio': 0,
                'porcentajes_operaciones_cliente': [],
                'porcentajes_kilos_cliente': [],
                'tendencia_semanal_json': '[]',
                'lead_times_por_bodega': [],
            }
        
        context.update({
            'total_solicitudes': stats['total'],
            'solicitudes_pendientes': stats['pendientes'],
            'solicitudes_en_despacho': stats['en_despacho'],
            'solicitudes_listo_despacho': stats['listo_despacho'],
            # 'solicitudes_embaladas': stats['embaladas'],  # descomentar junto con embaladas= en aggregate
            'solicitudes_despachadas': stats['despachadas'],
            'solicitudes_urgentes': stats['urgentes'],
            'solicitudes_recientes': Solicitud.objects.select_related('solicitante')[:10],
            
            # Estadísticas por estado
            'stats_por_estado': Solicitud.objects.values('estado').annotate(
                total=Count('id')
            ).order_by('estado'),
            
            # Indicadores de productividad
            'indicadores': indicadores,
            'periodo_actual': periodo_dias,
            'transporte_filtro': transporte_filtro,
        })
    
    elif user.es_bodega():
        # Bodega solo ve pendientes de SUS bodegas asignadas
        from django.db.models import Exists, OuterRef
        from solicitudes.models import SolicitudDetalle
        
        bodegas_usuario = user.get_bodegas_codigos()
        if bodegas_usuario:
            # Filtrar solo solicitudes que tienen detalles con bodegas asignadas al usuario
            detalles_pendientes = SolicitudDetalle.objects.filter(
                solicitud=OuterRef('pk'),
                bodega__in=bodegas_usuario,
                estado_bodega='pendiente'
            ).exclude(bodega='013')  # Bodega 013 es solo despacho
            
            solicitudes_pendientes = list(
                Solicitud.objects
                .filter(estado='pendiente')
                .annotate(tiene_pendientes=Exists(detalles_pendientes))
                .filter(tiene_pendientes=True)
                .select_related('solicitante')
                .order_by('fecha_solicitud', 'hora_solicitud')[:15]
            )
        else:
            # Si no tiene bodegas asignadas, no ver nada
            solicitudes_pendientes = []
        
        urgentes = sum(1 for s in solicitudes_pendientes if s.urgente)
        
        context.update({
            'solicitudes_pendientes': len(solicitudes_pendientes),
            'solicitudes_urgentes': urgentes,
            'listado_solicitudes': solicitudes_pendientes,
        })
    
    elif user.es_despacho():
        # Despacho solo ve en_despacho - Optimizado: 1 query en lugar de 3
        solicitudes_en_despacho = list(
            Solicitud.objects
            .filter(estado='en_despacho')
            .select_related('solicitante')
            .order_by('fecha_solicitud', 'hora_solicitud')[:15]
        )
        
        urgentes = sum(1 for s in solicitudes_en_despacho if s.urgente)
        
        context.update({
            'solicitudes_en_despacho': len(solicitudes_en_despacho),
            'solicitudes_urgentes': urgentes,
            'listado_solicitudes': solicitudes_en_despacho,
        })
    
    return render(request, 'dashboard.html', context)


@login_required
def perfil_usuario(request):
    """
    Vista del perfil del usuario
    """
    user = request.user

    if request.method == 'POST':
        # Solo administradores y superusuarios pueden cambiar su rol
        if user.es_admin():
            nuevo_rol = request.POST.get('rol')
            roles_validos = [rol[0] for rol in Usuario.ROLES]

            if nuevo_rol in roles_validos:
                user.rol = nuevo_rol
                user.save(update_fields=['rol'])
                messages.success(request, f'Rol actualizado a {user.get_rol_display()}')
            else:
                messages.error(request, 'Rol seleccionado no es válido')
        else:
            messages.error(request, 'No tienes permisos para cambiar el rol')

        return redirect('perfil')

    context = {
        'user': user,
        'roles': Usuario.ROLES,
    }
    return render(request, 'perfil.html', context)


def calcular_indicadores_productividad(periodo_dias=30, transporte_filtro=None):
    """
    Calcula los indicadores de productividad para el dashboard.
    
    Args:
        periodo_dias: Número de días hacia atrás para filtrar (default: 30)
        transporte_filtro: Filtro opcional por transporte (None = todos)
    
    Returns:
        Dict con todos los indicadores calculados
    
    Nota: Los resultados están cacheados por 5 minutos para mejorar performance.
    """
    from datetime import datetime, timedelta
    import hashlib
    import json
    
    # Crear clave de caché única basada en parámetros
    cache_key_data = {
        'periodo': periodo_dias,
        'transporte': transporte_filtro or 'todos',
    }
    cache_key_str = json.dumps(cache_key_data, sort_keys=True)
    cache_key_hash = hashlib.md5(cache_key_str.encode()).hexdigest()
    cache_key = f'indicadores_productividad_{cache_key_hash}'
    
    # Intentar obtener del caché (TTL: 5 minutos = 300 segundos)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    ahora = timezone.now()
    fecha_inicio = ahora - timedelta(days=periodo_dias)
    
    # ============================================================================
    # OPTIMIZACIÓN: 3 CONSULTAS MASIVAS + PROCESAMIENTO EN PYTHON
    # Reducimos de 900+ queries a solo 3 consultas masivas
    # ============================================================================
    
    # Constantes para bodegas del dashboard
    BODEGAS_DASHBOARD = ['013-01', '013-03', '013-05', '013-08', '013-09', '013-PP', '013-PS']
    
    # Base queryset para solicitudes del período
    # Solo considerar solicitudes DESPACHADAS (trabajo completado)
    solicitudes_base = Solicitud.objects.filter(
        created_at__gte=fecha_inicio,
        estado='despachado'  # Solo solicitudes despachadas
    )
    
    # Aplicar filtro de transporte si existe
    if transporte_filtro:
        solicitudes_base = solicitudes_base.filter(
            Q(bultos__transportista=transporte_filtro) | 
            Q(bultos__transportista_extra=transporte_filtro) |
            Q(transporte=transporte_filtro)
        ).distinct()
    
    # CONSULTA 1: Solicitudes completas con detalles y bultos precargados
    # PRECARGAR TODO: detalles y bultos en una sola query
    solicitudes_completas = solicitudes_base.prefetch_related(
        'detalles',
        'bultos'
    )
    
    # Convertir a lista UNA VEZ (evalúa la query y carga todo en memoria)
    solicitudes_list = list(solicitudes_completas)
    
    # CONSULTA 2: Detalles por bodega (para Lead Time Bodegas)
    
    detalles_bodegas = SolicitudDetalle.objects.filter(
        solicitud__created_at__gte=fecha_inicio,
        solicitud__estado='despachado',
        fecha_preparacion__isnull=False,
        bodega__in=BODEGAS_DASHBOARD
    ).select_related('solicitud')
    
    if transporte_filtro:
        detalles_bodegas = detalles_bodegas.filter(
            Q(solicitud__transporte=transporte_filtro) |
            Q(solicitud__bultos__transportista=transporte_filtro) |
            Q(solicitud__bultos__transportista_extra=transporte_filtro)
        ).distinct()
    
    detalles_bodegas_list = list(detalles_bodegas)
    
    # CONSULTA 3: Solicitudes listas para despacho (para Solicitudes en Despacho)
    # IMPORTANTE: Este indicador es diferente a los otros KPIs
    # - Los otros KPIs trabajan con solicitudes DESPACHADAS (completadas)
    # - Este indicador mide SOLICITUDES PENDIENTES (listo_despacho, aún no despachadas)
    # Una solicitud está lista cuando tiene estado 'listo_despacho'
    # Usamos fecha_preparacion de los detalles cuando pasan a bodega 013
    solicitudes_listas = Solicitud.objects.filter(
        estado='listo_despacho',
        created_at__gte=fecha_inicio
    ).select_related('solicitante').prefetch_related(
        'bultos',
        'detalles'
    )
    
    if transporte_filtro:
        solicitudes_listas = solicitudes_listas.filter(
            Q(transporte=transporte_filtro) |
            Q(bultos__transportista=transporte_filtro) |
            Q(bultos__transportista_extra=transporte_filtro)
        ).distinct()
    
    solicitudes_listas_list = list(solicitudes_listas)
    
    # ============================================================================
    # PROCESAMIENTO EN PYTHON (sin queries adicionales)
    # Todos los datos ya están precargados en memoria
    # ============================================================================
    
    # 1. LEAD TIME DE PREPARACIÓN
    # Mide: MAX(fecha_preparacion) de detalles − inicio_efectivo (max entre fecha/hora pedido y created_at)
    # Contar por SOLICITUD (1 vez). Se excluyen deltas negativos (fechas incoherentes).
    
    lead_times_prep = []
    # Diccionario para agrupar lead times por semana (año + número de semana ISO)
    lead_times_por_semana = {}
    
    # PROCESAMIENTO EN PYTHON: Los detalles ya están en memoria (prefetch_related)
    for solicitud in solicitudes_list:
        # Los detalles ya están en memoria, no necesitamos query adicional
        fechas_prep = [
            d.fecha_preparacion 
            for d in solicitud.detalles.all() 
            if d.fecha_preparacion
        ]
        
        if fechas_prep:
            fecha_prep_max = max(fechas_prep)
            inicio = inicio_efectivo_lead_time(solicitud)
            if not inicio:
                continue
            delta = fecha_prep_max - inicio
            horas = delta.total_seconds() / 3600
            if not _lead_horas_validas(horas):
                continue
            lead_times_prep.append(horas)
            
            # Agrupar por SEMANA ISO (usar fecha de preparación como referencia)
            fecha_prep = fecha_prep_max.date()
            iso_year, iso_week, iso_day = fecha_prep.isocalendar()
            
            # Clave única por semana: "2026-W02" (año-semana)
            semana_key = f"{iso_year}-W{iso_week:02d}"
            
            if semana_key not in lead_times_por_semana:
                lead_times_por_semana[semana_key] = {
                    'valores': [],
                    'iso_year': iso_year,
                    'iso_week': iso_week,
                }
            lead_times_por_semana[semana_key]['valores'].append(horas)
    
    lt_prep_promedio = sum(lead_times_prep) / len(lead_times_prep) if lead_times_prep else 0
    lt_prep_min = min(lead_times_prep) if lead_times_prep else 0
    lt_prep_max = max(lead_times_prep) if lead_times_prep else 0
    
    # Calcular datos semanales para el gráfico de tendencia
    # Ordenar por semana y calcular promedio, mínimo y máximo por semana
    tendencia_semanal_prep = []
    for semana_key in sorted(lead_times_por_semana.keys()):
        datos_semana = lead_times_por_semana[semana_key]
        valores = datos_semana['valores']
        iso_year = datos_semana['iso_year']
        iso_week = datos_semana['iso_week']
        
        # Calcular primer y último día de la semana para display
        # ISO: lunes es día 1, domingo es día 7
        primer_dia = datetime.strptime(f'{iso_year}-W{iso_week:02d}-1', '%G-W%V-%u').date()
        ultimo_dia = primer_dia + timedelta(days=6)  # domingo
        
        # Formato de display: "Sem 2: 06/01-12/01"
        fecha_display = f"Sem {iso_week}: {primer_dia.strftime('%d/%m')}-{ultimo_dia.strftime('%d/%m')}"
        
        tendencia_semanal_prep.append({
            'semana': semana_key,  # "2026-W02"
            'semana_numero': iso_week,
            'fecha_display': fecha_display,  # "Sem 2: 06/01-12/01"
            'fecha_inicio': primer_dia.strftime('%Y-%m-%d'),
            'fecha_fin': ultimo_dia.strftime('%Y-%m-%d'),
            'promedio': float(sum(valores) / len(valores)),
            'minimo': float(min(valores)),
            'maximo': float(max(valores)),
            'cantidad': len(valores)
        })
    
    # Serializar a JSON string para el template (siempre una lista, aunque esté vacía)
    tendencia_semanal_json = json.dumps(tendencia_semanal_prep, ensure_ascii=False) if tendencia_semanal_prep else '[]'
    
    # 1.5. ESTADÍSTICAS POR CLIENTE
    # Agrupar solicitudes por cliente para calcular porcentajes
    from collections import defaultdict
    
    # Definir sucursales con sus variaciones posibles
    sucursales_map = {
        'SUC CALAMA': ['SUC CALAMA', 'SUCURSAL CALAMA', 'SUC CALAMA', 'Suc Calama', 'suc calama'],
        'SUC ANTOFAGASTA': ['SUC ANTOFAGASTA', 'SUCURSAL ANTOFAGASTA', 'SUC ANTOFA', 'Suc Antofagasta', 'suc antofagasta', 'sucursal antofagasta'],
        'SUC PTO MONTT': ['SUC PTO MONTT', 'SUC PTO. MONTT', 'SUC PUERTO MONTT', 'SUCURSAL PTO MONTT', 'Suc Pto Montt', 'suc pto montt'],
        'SUC LOS ANGELES': ['SUC LOS ANGELES', 'SUCURSAL LOS ANGELES', 'SUC LOS ÁNGELES', 'Suc Los Angeles', 'suc los angeles'],
    }
    
    def normalizar_cliente(cliente):
        """Normaliza el nombre del cliente para identificar sucursales"""
        cliente_upper = cliente.upper().strip()
        # Buscar coincidencias para cada sucursal
        for sucursal_norm, variaciones in sucursales_map.items():
            for variacion in variaciones:
                if variacion.upper() in cliente_upper or cliente_upper in variacion.upper():
                    return sucursal_norm
        return None
    
    # Estadísticas de operaciones por categoría (sucursal, Camión PESCO, Retira cliente, u OTROS)
    # Camión PESCO / Retira cliente: se separan de OTROS para visibilidad en las tortas del dashboard
    operaciones_sucursales = defaultdict(int)
    operaciones_camion_pesco = 0
    operaciones_retira_cliente = 0
    operaciones_otros = []
    operaciones_otros_por_cliente = defaultdict(int)
    
    for solicitud in solicitudes_list:
        cliente = solicitud.cliente
        transporte = (solicitud.transporte or '').strip().upper()
        
        if transporte == 'PESCO':
            operaciones_camion_pesco += 1
        elif _es_transporte_retira_cliente(solicitud.transporte):
            operaciones_retira_cliente += 1
        elif normalizar_cliente(cliente):
            sucursal_norm = normalizar_cliente(cliente)
            operaciones_sucursales[sucursal_norm] += 1
        else:
            operaciones_otros_por_cliente[cliente] += 1
    
    total_operaciones = len(solicitudes_list)
    
    for cliente, operaciones in operaciones_otros_por_cliente.items():
        porcentaje = (operaciones / total_operaciones * 100) if total_operaciones > 0 else 0
        operaciones_otros.append({
            'cliente': cliente,
            'operaciones': operaciones,
            'porcentaje': round(porcentaje, 2)
        })
    
    # Crear lista de porcentajes agrupados (sucursales + Camión PESCO + OTROS)
    porcentajes_operaciones = []
    total_otros = sum(item['operaciones'] for item in operaciones_otros)
    
    # Orden fijo para los gráficos (sucursales + Camión PESCO + OTROS)
    ORDEN_SUCURSALES = [
        'SUC ANTOFAGASTA',
        'SUC CALAMA',
        'SUC PTO MONTT',
        'SUC LOS ANGELES',
        'Camión PESCO',  # Transporte propio - separado de OTROS
        'Retira cliente',
        'OTROS'
    ]
    
    # Usar un set para evitar duplicados
    categorias_agregadas = set()
    
    # Agregar sucursales en el orden especificado
    for sucursal in ['SUC ANTOFAGASTA', 'SUC CALAMA', 'SUC PTO MONTT', 'SUC LOS ANGELES']:
        if sucursal in operaciones_sucursales and sucursal not in categorias_agregadas:
            ops = operaciones_sucursales[sucursal]
            porcentaje = (ops / total_operaciones * 100) if total_operaciones > 0 else 0
            porcentajes_operaciones.append({
                'cliente': sucursal,
                'operaciones': ops,
                'porcentaje': round(porcentaje, 2)
            })
            categorias_agregadas.add(sucursal)
    
    # Agregar cualquier otra sucursal no contemplada (por si acaso)
    for sucursal, ops in sorted(operaciones_sucursales.items(), key=lambda x: x[1], reverse=True):
        if sucursal not in categorias_agregadas:
            porcentaje = (ops / total_operaciones * 100) if total_operaciones > 0 else 0
            porcentajes_operaciones.append({
                'cliente': sucursal,
                'operaciones': ops,
                'porcentaje': round(porcentaje, 2)
            })
            categorias_agregadas.add(sucursal)
    
    # Agregar Camión PESCO (transporte propio)
    if operaciones_camion_pesco > 0:
        porcentaje = (operaciones_camion_pesco / total_operaciones * 100) if total_operaciones > 0 else 0
        porcentajes_operaciones.append({
            'cliente': 'Camión PESCO',
            'operaciones': operaciones_camion_pesco,
            'porcentaje': round(porcentaje, 2)
        })
    
    if operaciones_retira_cliente > 0:
        porcentaje_rc = (operaciones_retira_cliente / total_operaciones * 100) if total_operaciones > 0 else 0
        porcentajes_operaciones.append({
            'cliente': 'Retira cliente',
            'operaciones': operaciones_retira_cliente,
            'porcentaje': round(porcentaje_rc, 2)
        })
    
    # Agregar OTROS al final
    if total_otros > 0:
        porcentaje_otros = (total_otros / total_operaciones * 100) if total_operaciones > 0 else 0
        porcentajes_operaciones.append({
            'cliente': 'OTROS',
            'operaciones': total_otros,
            'porcentaje': round(porcentaje_otros, 2)
        })
    
    # Estadísticas de kilos volumétricos por categoría (sucursal, Camión PESCO, Retira cliente, u OTROS)
    kilos_por_cliente = defaultdict(lambda: Decimal('0.00'))
    kilos_camion_pesco = Decimal('0.00')
    kilos_retira_cliente = Decimal('0.00')
    kilos_otros_detalle = defaultdict(lambda: Decimal('0.00'))
    clientes_sin_medidas = set()
    clientes_otros_sin_medidas = set()
    
    for solicitud in solicitudes_list:
        cliente = solicitud.cliente
        transporte = (solicitud.transporte or '').strip().upper()
        kilos_solicitud = Decimal('0.00')
        
        for bulto in solicitud.bultos.all():
            if bulto.largo_cm and bulto.ancho_cm and bulto.alto_cm and \
               bulto.largo_cm > 0 and bulto.ancho_cm > 0 and bulto.alto_cm > 0:
                volumen_cm3 = bulto.largo_cm * bulto.ancho_cm * bulto.alto_cm
                peso_volumetrico = volumen_cm3 / Decimal('6000')
                peso_real = bulto.peso_total if bulto.peso_total else Decimal('0.00')
                peso_cobrable = max(peso_real, peso_volumetrico)
            else:
                peso_cobrable = bulto.peso_total if bulto.peso_total else Decimal('0.00')
            
            kilos_solicitud += peso_cobrable
        
        if transporte == 'PESCO':
            kilos_camion_pesco += kilos_solicitud
        elif _es_transporte_retira_cliente(solicitud.transporte):
            kilos_retira_cliente += kilos_solicitud
        elif normalizar_cliente(cliente):
            sucursal_norm = normalizar_cliente(cliente)
            kilos_por_cliente[sucursal_norm] += kilos_solicitud
        else:
            kilos_otros_detalle[cliente] += kilos_solicitud
    
    # Calcular total de kilos (sucursales + Camión PESCO + Retira cliente + OTROS)
    total_kilos = (
        sum(kilos_por_cliente.values())
        + kilos_camion_pesco
        + kilos_retira_cliente
        + sum(kilos_otros_detalle.values())
    )
    
    # Si total_kilos es 0, significa que no hay kilos en ninguna solicitud
    # En ese caso, todos los porcentajes serán 0% pero las solicitudes se contarán igual
    porcentajes_kilos = []
    
    # Usar un set para evitar duplicados
    sucursales_kilos_agregadas = set()
    
    # Agregar sucursales en el orden especificado (incluir incluso si tienen 0 kilos)
    for sucursal in ORDEN_SUCURSALES:
        if sucursal in kilos_por_cliente and sucursal not in sucursales_kilos_agregadas:
            kilos = kilos_por_cliente[sucursal]
            # Calcular porcentaje sobre el total (puede ser 0% si no hay kilos)
            porcentaje = (float(kilos) / float(total_kilos) * 100) if total_kilos > 0 else 0
            porcentajes_kilos.append({
                'cliente': sucursal,
                'kilos_volumetricos': float(kilos),
                'porcentaje': round(porcentaje, 2)
            })
            sucursales_kilos_agregadas.add(sucursal)
    
    # Agregar cualquier otra sucursal no contemplada en el orden (por si acaso)
    for sucursal, kilos in sorted(kilos_por_cliente.items(), key=lambda x: x[1], reverse=True):
        if sucursal not in ORDEN_SUCURSALES and sucursal not in sucursales_kilos_agregadas:
            porcentaje = (float(kilos) / float(total_kilos) * 100) if total_kilos > 0 else 0
            porcentajes_kilos.append({
                'cliente': sucursal,
                'kilos_volumetricos': float(kilos),
                'porcentaje': round(porcentaje, 2)
            })
            sucursales_kilos_agregadas.add(sucursal)
    
    # Agregar Camión PESCO (transporte propio)
    if kilos_camion_pesco > 0:
        porcentaje = (float(kilos_camion_pesco) / float(total_kilos) * 100) if total_kilos > 0 else 0
        porcentajes_kilos.append({
            'cliente': 'Camión PESCO',
            'kilos_volumetricos': float(kilos_camion_pesco),
            'porcentaje': round(porcentaje, 2)
        })
    
    if kilos_retira_cliente > 0:
        porcentaje = (float(kilos_retira_cliente) / float(total_kilos) * 100) if total_kilos > 0 else 0
        porcentajes_kilos.append({
            'cliente': 'Retira cliente',
            'kilos_volumetricos': float(kilos_retira_cliente),
            'porcentaje': round(porcentaje, 2)
        })
    
    # Agregar OTROS (suma de todos los clientes no sucursales)
    # IMPORTANTE: Incluir OTROS incluso si tiene 0 kilos, para que los porcentajes sumen 100%
    total_otros_kilos = sum(kilos_otros_detalle.values())
    porcentaje_otros = (float(total_otros_kilos) / float(total_kilos) * 100) if total_kilos > 0 else 0
    porcentajes_kilos.append({
        'cliente': 'OTROS',
        'kilos_volumetricos': float(total_otros_kilos),
        'porcentaje': round(porcentaje_otros, 2)
    })
    
    # Agregar clientes sin medidas (para información) al final
    todos_sin_medidas = clientes_sin_medidas | clientes_otros_sin_medidas
    if todos_sin_medidas:
        porcentajes_kilos.append({
            'cliente': 'Sin medidas (retiro cliente, etc.)',
            'kilos_volumetricos': 0.0,
            'porcentaje': 0.0,
            'cantidad_clientes': len(todos_sin_medidas)
        })
    
    # Crear desglose detallado de OTROS
    porcentajes_otros_detalle_kilos = []
    for cliente, kilos in sorted(kilos_otros_detalle.items(), key=lambda x: x[1], reverse=True):
        if kilos > 0:
            porcentaje = (float(kilos) / float(total_otros_kilos) * 100) if total_otros_kilos > 0 else 0
            porcentajes_otros_detalle_kilos.append({
                'cliente': cliente,
                'kilos_volumetricos': float(kilos),
                'porcentaje': round(porcentaje, 2)
            })
    
    # Agregar clientes OTROS sin medidas al desglose
    if clientes_otros_sin_medidas:
        porcentajes_otros_detalle_kilos.append({
            'cliente': 'Sin medidas (retiro cliente, etc.)',
            'kilos_volumetricos': 0.0,
            'porcentaje': 0.0,
            'cantidad_clientes': len(clientes_otros_sin_medidas)
        })
    
    # 2. LEAD TIME DE EMBALAJE
    # Mide: Desde que termina la preparación (MAX fecha_preparacion) hasta que se embala (MAX fecha_embalaje)
    # CORRECCIÓN: Contar por SOLICITUD (1 vez), no por bulto
    # OPTIMIZADO: Usar solicitudes_list en memoria (bultos y detalles ya precargados)
    
    lead_times_emb = []
    for solicitud in solicitudes_list:
        # Los bultos ya están en memoria (prefetch_related)
        bultos_embalados = [
            b for b in solicitud.bultos.all()
            if b.fecha_embalaje and b.estado != 'cancelado'
        ]
        
        if bultos_embalados:
            # Calcular MAX en Python (no query adicional)
            fecha_emb_max = max(b.fecha_embalaje for b in bultos_embalados)
            
            # Los detalles ya están en memoria (prefetch_related)
            fechas_prep = [
                d.fecha_preparacion 
                for d in solicitud.detalles.all() 
                if d.fecha_preparacion
            ]
            
            fecha_fin_preparacion = max(fechas_prep) if fechas_prep else inicio_efectivo_lead_time(solicitud)
            
            if fecha_fin_preparacion:
                # Lead Time = fecha_embalaje (MAX) - fecha_fin_preparacion (MAX)
                delta = fecha_emb_max - fecha_fin_preparacion
                horas = delta.total_seconds() / 3600
                if horas >= 0 and _lead_horas_validas(horas):
                    lead_times_emb.append(horas)
    
    lt_emb_promedio = sum(lead_times_emb) / len(lead_times_emb) if lead_times_emb else 0
    lt_emb_min = min(lead_times_emb) if lead_times_emb else 0
    lt_emb_max = max(lead_times_emb) if lead_times_emb else 0
    
    # 3. LEAD TIME TOTAL (SOLICITUD COMPLETA)
    # Mide: Desde inicio_efectivo hasta MAX(fecha_envio/fecha_entrega) con bultos finalizados
    # CORRECCIÓN: Contar por SOLICITUD (1 vez), no por bulto
    # Solo usamos solicitudes con bultos finalizados porque cuando la solicitud pasa a 'despachado',
    # todos sus bultos se finalizan automáticamente
    # OPTIMIZADO: Usar solicitudes_list en memoria (bultos ya precargados)
    
    lead_times_total = []
    for solicitud in solicitudes_list:
        # Los bultos ya están en memoria (prefetch_related)
        bultos_final = [
            b for b in solicitud.bultos.all()
            if b.estado == 'finalizado' and b.fecha_envio
        ]
        
        if bultos_final:
            inicio = inicio_efectivo_lead_time(solicitud)
            if not inicio:
                continue
            fechas_fin = []
            for bulto in bultos_final:
                fecha_fin = bulto.fecha_envio or bulto.fecha_entrega
                if fecha_fin:
                    fechas_fin.append(fecha_fin)
            
            if fechas_fin:
                fecha_fin_max = max(fechas_fin)
                delta = fecha_fin_max - inicio
                horas = delta.total_seconds() / 3600
                if _lead_horas_validas(horas):
                    lead_times_total.append(horas)
    
    lt_total_promedio = sum(lead_times_total) / len(lead_times_total) if lead_times_total else 0
    lt_total_min = min(lead_times_total) if lead_times_total else 0
    lt_total_max = max(lead_times_total) if lead_times_total else 0
    
    # Obtener nombres de bodegas desde el modelo (una sola query)
    from .models import Bodega
    bodegas_info = {
        b.codigo: b.nombre 
        for b in Bodega.objects.filter(activa=True)
    }
    
    # Calcular LEAD TIME DE PREPARACIÓN por bodega
    # INICIALIZAR TODAS las bodegas con 0 operaciones
    lead_times_por_bodega = {}
    for bodega_codigo in BODEGAS_DASHBOARD:
        lead_times_por_bodega[bodega_codigo] = {
            'codigo': bodega_codigo,
            'nombre': bodegas_info.get(bodega_codigo, 'Nombre no disponible'),
            'lead_times_horas': [],
            'cantidad_operaciones': 0
        }
    
    # OPTIMIZADO: Usar detalles_bodegas_list (ya precargados en consulta 2)
    # Agregar lead times calculados
    for detalle in detalles_bodegas_list:
        bodega_codigo = detalle.bodega.strip() if detalle.bodega else ''
        
        # Filtrar: solo bodegas de uso cotidiano
        if not bodega_codigo or bodega_codigo not in BODEGAS_DASHBOARD:
            continue
        
        if detalle.fecha_preparacion:
            sol = detalle.solicitud
            inicio = inicio_efectivo_lead_time(sol)
            if inicio:
                delta = detalle.fecha_preparacion - inicio
                horas = delta.total_seconds() / 3600
                if _lead_horas_validas(horas):
                    lead_times_por_bodega[bodega_codigo]['lead_times_horas'].append(horas)
                    lead_times_por_bodega[bodega_codigo]['cantidad_operaciones'] += 1
    
    # Formatear datos de lead time por bodega - INCLUIR TODAS
    lead_time_bodegas = []
    for bodega_codigo in BODEGAS_DASHBOARD:  # Iterar en el orden definido
        datos = lead_times_por_bodega[bodega_codigo]
        
        if datos['lead_times_horas']:
            # Calcular promedio si hay datos
            horas_prom = sum(datos['lead_times_horas']) / len(datos['lead_times_horas'])
            dias_prom = horas_prom / 24  # Convertir a días
            horas_min = min(datos['lead_times_horas'])
            horas_max = max(datos['lead_times_horas'])
        else:
            # Sin datos: 0 operaciones
            horas_prom = 0
            dias_prom = 0
            horas_min = 0
            horas_max = 0
        
        lead_time_bodegas.append({
            'bodega_codigo': bodega_codigo,
            'bodega_nombre': datos['nombre'],
            'lead_time_horas': horas_prom,
            'lead_time_dias': dias_prom,
            'cantidad_operaciones': datos['cantidad_operaciones'],
            'horas_min': horas_min,
            'horas_max': horas_max,
        })
    
    # NO ordenar - mantener el orden definido en BODEGAS_DASHBOARD
    # Esto asegura que los datos coincidan con los labels en el frontend
    
    # ============================================================================
    # SOLICITUDES EN DESPACHO POR TRANSPORTE (Horas Laborales + Días)
    # ============================================================================
    # IMPORTANTE: Usa fecha_preparacion cuando el producto pasa a bodega 013
    
    # Agrupar por transporte y calcular métricas
    solicitudes_por_transporte = {}
    
    # OPTIMIZADO: Usar solicitudes_listas_list (ya precargados en consulta 3)
    # Primero, recopilar todos los códigos únicos para hacer batch query de precios
    todos_codigos = set()
    for solicitud in solicitudes_listas_list:
        for detalle in solicitud.detalles.all():
            todos_codigos.add(detalle.codigo)
    
    # Batch query para precios
    precios_cache = {}
    if todos_codigos:
        stocks = Stock.objects.filter(codigo__in=list(todos_codigos)).values('codigo', 'precio')
        for stock in stocks:
            if stock['codigo'] not in precios_cache and stock.get('precio'):
                precios_cache[stock['codigo']] = stock['precio']
    
    # Procesar SOLICITUDES (no bultos)
    for solicitud in solicitudes_listas_list:
        # Determinar transporte (prioridad: bulto.transportista_extra > bulto.transportista > solicitud.transporte)
        transporte_slug = 'Sin transporte'
        fecha_preparacion_solicitud = None
        
        # Buscar la fecha_preparacion más reciente de los detalles
        # (especialmente los que tienen bodega='013' o fueron transferidos a 013)
        detalles_con_fecha = [
            d for d in solicitud.detalles.all() 
            if d.fecha_preparacion is not None
        ]
        
        if detalles_con_fecha:
            # Tomar la fecha_preparacion más reciente
            detalle_mas_reciente = max(
                detalles_con_fecha,
                key=lambda d: d.fecha_preparacion
            )
            fecha_preparacion_solicitud = detalle_mas_reciente.fecha_preparacion
        
        # Determinar transporte desde bultos o solicitud
        bultos_solicitud = list(solicitud.bultos.all())
        if bultos_solicitud:
            # Tomar el primer bulto con transporte definido
            for bulto in bultos_solicitud:
                transporte_slug = (
                    bulto.transportista_extra or 
                    bulto.transportista or 
                    solicitud.transporte or 
                    'Sin transporte'
                )
                if transporte_slug != 'Sin transporte':
                    break
        else:
            transporte_slug = solicitud.transporte or 'Sin transporte'
        
        # Obtener nombre legible del transporte
        transporte = TransporteConfig.etiqueta(transporte_slug) if transporte_slug != 'Sin transporte' else 'Sin transporte'
        
        if transporte not in solicitudes_por_transporte:
            solicitudes_por_transporte[transporte] = {
                'solicitudes': set(),
                'horas_laborales': [],
                'dias_calendario': [],
                'valor_usd': Decimal('0.00')
            }
        
        # Agregar la solicitud única
        solicitudes_por_transporte[transporte]['solicitudes'].add(solicitud.id)
        
        # Calcular horas laborales y días calendario desde fecha_preparacion
        # (cuando el producto pasa a bodega 013)
        if fecha_preparacion_solicitud:
            # Horas laborales (excluyendo fines de semana, 8h/día)
            horas_lab = calcular_horas_laborales(fecha_preparacion_solicitud, ahora)
            solicitudes_por_transporte[transporte]['horas_laborales'].append(horas_lab)
            
            # Días calendario (para referencia)
            dias_cal = (ahora - fecha_preparacion_solicitud).total_seconds() / 86400
            solicitudes_por_transporte[transporte]['dias_calendario'].append(dias_cal)
        
        # Valorizar todos los detalles de la solicitud
        for detalle in solicitud.detalles.all():
            precio = precios_cache.get(detalle.codigo)
            if precio:
                valor = Decimal(str(precio)) * detalle.cantidad
                solicitudes_por_transporte[transporte]['valor_usd'] += valor
    
    # Formatear datos de solicitudes en despacho
    solicitudes_despacho = []
    for transporte, datos in solicitudes_por_transporte.items():
        # Calcular promedios
        horas_prom = sum(datos['horas_laborales']) / len(datos['horas_laborales']) if datos['horas_laborales'] else 0
        dias_lab_prom = horas_prom / 8  # Convertir horas a días laborales (8h = 1 día)
        dias_cal_prom = sum(datos['dias_calendario']) / len(datos['dias_calendario']) if datos['dias_calendario'] else 0
        
        solicitudes_despacho.append({
            'transporte': transporte,
            'cantidad_solicitudes': len(datos['solicitudes']),
            'valor_usd': datos['valor_usd'],
            'horas_laborales': horas_prom,
            'dias_laborales': dias_lab_prom,
            'dias_calendario': dias_cal_prom,
            'horas_min': min(datos['horas_laborales']) if datos['horas_laborales'] else 0,
            'horas_max': max(datos['horas_laborales']) if datos['horas_laborales'] else 0,
            'dias_min': min(datos['horas_laborales']) / 8 if datos['horas_laborales'] else 0,
            'dias_max': max(datos['horas_laborales']) / 8 if datos['horas_laborales'] else 0,
        })
    
    # Ordenar por cantidad de solicitudes descendente
    solicitudes_despacho.sort(key=lambda x: x['cantidad_solicitudes'], reverse=True)
    
    # Obtener lista de transportes únicos para el dropdown
    transportes_disponibles = list(set(
        list(Bulto.objects.exclude(transportista='').values_list('transportista', flat=True)) +
        list(Bulto.objects.exclude(transportista_extra='').values_list('transportista_extra', flat=True)) +
        list(Solicitud.objects.exclude(transporte='').values_list('transporte', flat=True))
    ))
    transportes_disponibles = [t for t in transportes_disponibles if t]  # Filtrar vacíos
    # Siempre incluir PESCO (Camión PESCO) en el filtro por ser transporte clave de la operación
    if 'PESCO' not in transportes_disponibles:
        transportes_disponibles.append('PESCO')
    transportes_disponibles.sort()
    
    # Convertir a JSON para evitar problemas de renderizado en el template
    # Esto previene duplicados y problemas con caracteres especiales
    porcentajes_operaciones_json = json.dumps(porcentajes_operaciones, ensure_ascii=False)
    porcentajes_kilos_json = json.dumps(porcentajes_kilos, ensure_ascii=False)
    
    result = {
        'lead_time_preparacion': {
            'promedio_horas': lt_prep_promedio,
            'promedio_dias': lt_prep_promedio / 24,
            'min_horas': lt_prep_min,
            'min_dias': lt_prep_min / 24,
            'max_horas': lt_prep_max,
            'max_dias': lt_prep_max / 24,
            'total_registros': len(lead_times_prep),
            'tendencia_semanal': tendencia_semanal_prep,
            'tendencia_semanal_json': tendencia_semanal_json
        },
        'lead_time_embalaje': {
            'promedio_horas': lt_emb_promedio,
            'promedio_dias': lt_emb_promedio / 24,
            'min_horas': lt_emb_min,
            'min_dias': lt_emb_min / 24,
            'max_horas': lt_emb_max,
            'max_dias': lt_emb_max / 24,
            'total_registros': len(lead_times_emb)
        },
        'lead_time_total': {
            'promedio_horas': lt_total_promedio,
            'promedio_dias': lt_total_promedio / 24,
            'min_horas': lt_total_min,
            'min_dias': lt_total_min / 24,
            'max_horas': lt_total_max,
            'max_dias': lt_total_max / 24,
            'total_registros': len(lead_times_total)
        },
        'lead_time_bodegas': lead_time_bodegas,
        'solicitudes_en_despacho': solicitudes_despacho,
        'transportes_disponibles': transportes_disponibles,
        'periodo_dias': periodo_dias,
        # Estadísticas por cliente (agrupadas: sucursales + OTROS)
        'porcentajes_operaciones_cliente': porcentajes_operaciones,
        'porcentajes_kilos_cliente': porcentajes_kilos,
        # Versiones JSON para evitar problemas de renderizado en template
        'porcentajes_operaciones_cliente_json': porcentajes_operaciones_json,
        'porcentajes_kilos_cliente_json': porcentajes_kilos_json,
        # Desglose detallado de OTROS
        'porcentajes_operaciones_otros': operaciones_otros,
        'porcentajes_kilos_otros': porcentajes_otros_detalle_kilos
    }
    
    # Guardar en caché por 5 minutos (300 segundos)
    cache.set(cache_key, result, timeout=300)
    
    return result
