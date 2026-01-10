"""
Vistas principales del Sistema PESCO
Basado en la arquitectura de sistemaGDV
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Avg, Min, Max, Sum, F, ExpressionWrapper, DurationField
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta, datetime
from decimal import Decimal
from solicitudes.models import Solicitud, SolicitudDetalle
from despacho.models import Bulto
from bodega.models import Stock
from .models import Usuario
from configuracion.models import TransporteConfig


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
    
    context = {
        'user': user,
        'hoy': fecha_chile.date(),
    }
    
    # Obtener parámetros de filtro
    periodo = request.GET.get('periodo', '30')  # Default: últimos 30 días
    try:
        periodo_dias = int(periodo)
    except (ValueError, TypeError):
        periodo_dias = 30
    
    transporte_filtro = request.GET.get('transporte', None)
    if transporte_filtro == '':
        transporte_filtro = None
    
    if user.es_admin():
        # Admin ve todo - Optimizado: 1 query en lugar de 6
        stats = Solicitud.objects.aggregate(
            total=Count('id'),
            pendientes=Count('id', filter=Q(estado='pendiente')),
            en_despacho=Count('id', filter=Q(estado='en_despacho')),
            embaladas=Count('id', filter=Q(estado='embalado')),
            urgentes=Count('id', filter=Q(
                urgente=True,
                estado__in=['pendiente', 'en_despacho', 'embalado']
            ))
        )
        
        # Calcular indicadores de productividad
        indicadores = calcular_indicadores_productividad(
            periodo_dias=periodo_dias,
            transporte_filtro=transporte_filtro
        )
        
        context.update({
            'total_solicitudes': stats['total'],
            'solicitudes_pendientes': stats['pendientes'],
            'solicitudes_en_despacho': stats['en_despacho'],
            'solicitudes_embaladas': stats['embaladas'],
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
                .select_related('solicitante')[:15]
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
            .select_related('solicitante')[:15]
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
    
    # Base queryset para solicitudes del período
    # Solo considerar solicitudes DESPACHADAS (trabajo completado)
    solicitudes_base = Solicitud.objects.filter(
        created_at__gte=fecha_inicio,
        estado='despachado'  # Solo solicitudes despachadas
    )
    
    # 1. LEAD TIME DE PREPARACIÓN
    # Tiempo desde created_at hasta fecha_preparacion del primer detalle preparado
    detalles_preparados = SolicitudDetalle.objects.filter(
        solicitud__in=solicitudes_base,
        fecha_preparacion__isnull=False
    ).select_related('solicitud')
    
    lead_times_prep = []
    # Diccionario para agrupar lead times por día (fecha de preparación)
    lead_times_por_dia = {}
    
    for detalle in detalles_preparados:
        if detalle.fecha_preparacion and detalle.solicitud.created_at:
            delta = detalle.fecha_preparacion - detalle.solicitud.created_at
            horas = delta.total_seconds() / 3600
            lead_times_prep.append(horas)
            
            # Agrupar por día (usar fecha de preparación como referencia)
            fecha_dia = detalle.fecha_preparacion.date()
            if fecha_dia not in lead_times_por_dia:
                lead_times_por_dia[fecha_dia] = []
            lead_times_por_dia[fecha_dia].append(horas)
    
    lt_prep_promedio = sum(lead_times_prep) / len(lead_times_prep) if lead_times_prep else 0
    lt_prep_min = min(lead_times_prep) if lead_times_prep else 0
    lt_prep_max = max(lead_times_prep) if lead_times_prep else 0
    
    # Calcular datos diarios para el gráfico de tendencia
    # Ordenar por fecha y calcular promedio, mínimo y máximo por día
    tendencia_diaria_prep = []
    for fecha in sorted(lead_times_por_dia.keys()):
        valores_dia = lead_times_por_dia[fecha]
        tendencia_diaria_prep.append({
            'fecha': fecha.strftime('%Y-%m-%d'),
            'fecha_display': fecha.strftime('%d/%m'),
            'promedio': float(sum(valores_dia) / len(valores_dia)),
            'minimo': float(min(valores_dia)),
            'maximo': float(max(valores_dia)),
            'cantidad': len(valores_dia)
        })
    
    # Serializar a JSON string para el template (siempre una lista, aunque esté vacía)
    tendencia_diaria_json = json.dumps(tendencia_diaria_prep, ensure_ascii=False) if tendencia_diaria_prep else '[]'
    
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
    
    # Estadísticas de operaciones por cliente (sin agrupar)
    solicitudes_por_cliente = solicitudes_base.values('cliente').annotate(
        total_operaciones=Count('id')
    ).order_by('-total_operaciones')
    
    total_operaciones = solicitudes_base.count()
    
    # Agrupar por sucursales y OTROS
    operaciones_sucursales = defaultdict(int)
    operaciones_otros = []
    
    for item in solicitudes_por_cliente:
        cliente = item['cliente']
        operaciones = item['total_operaciones']
        sucursal_norm = normalizar_cliente(cliente)
        
        if sucursal_norm:
            operaciones_sucursales[sucursal_norm] += operaciones
        else:
            porcentaje = (operaciones / total_operaciones * 100) if total_operaciones > 0 else 0
            operaciones_otros.append({
                'cliente': cliente,
                'operaciones': operaciones,
                'porcentaje': round(porcentaje, 2)
            })
    
    # Crear lista de porcentajes agrupados (sucursales + OTROS)
    porcentajes_operaciones = []
    total_otros = sum(item['operaciones'] for item in operaciones_otros)
    
    # Agregar sucursales
    for sucursal, operaciones in sorted(operaciones_sucursales.items(), key=lambda x: x[1], reverse=True):
        porcentaje = (operaciones / total_operaciones * 100) if total_operaciones > 0 else 0
        porcentajes_operaciones.append({
            'cliente': sucursal,
            'operaciones': operaciones,
            'porcentaje': round(porcentaje, 2)
        })
    
    # Agregar OTROS
    if total_otros > 0:
        porcentaje_otros = (total_otros / total_operaciones * 100) if total_operaciones > 0 else 0
        porcentajes_operaciones.append({
            'cliente': 'OTROS',
            'operaciones': total_otros,
            'porcentaje': round(porcentaje_otros, 2)
        })
    
    # Estadísticas de kilos volumétricos por cliente
    # Obtener todos los bultos de las solicitudes del período
    from despacho.models import Bulto
    
    bultos_periodo = Bulto.objects.filter(
        solicitud__in=solicitudes_base
    ).select_related('solicitud')
    
    # Calcular kilos volumétricos por cliente
    kilos_por_cliente = defaultdict(lambda: Decimal('0.00'))
    kilos_otros_detalle = defaultdict(lambda: Decimal('0.00'))
    clientes_sin_medidas = set()
    clientes_otros_sin_medidas = set()
    
    for bulto in bultos_periodo:
        cliente = bulto.solicitud.cliente
        
        # Calcular peso volumétrico
        # Fórmula: (largo × ancho × alto en cm) / 6000
        if bulto.largo_cm and bulto.ancho_cm and bulto.alto_cm and \
           bulto.largo_cm > 0 and bulto.ancho_cm > 0 and bulto.alto_cm > 0:
            volumen_cm3 = bulto.largo_cm * bulto.ancho_cm * bulto.alto_cm
            peso_volumetrico = volumen_cm3 / Decimal('6000')
            
            # Peso cobrable = mayor entre real y volumétrico
            peso_real = bulto.peso_total if bulto.peso_total else Decimal('0.00')
            peso_cobrable = max(peso_real, peso_volumetrico)
        else:
            # Si no tiene dimensiones, usar solo peso real
            peso_cobrable = bulto.peso_total if bulto.peso_total else Decimal('0.00')
            if peso_cobrable == 0:
                # Marcar como sin medidas
                if normalizar_cliente(cliente):
                    clientes_sin_medidas.add(cliente)
                else:
                    clientes_otros_sin_medidas.add(cliente)
                continue  # No sumar bultos sin peso ni dimensiones
        
        # Agrupar por sucursal normalizada
        sucursal_norm = normalizar_cliente(cliente)
        
        if sucursal_norm:
            # Es una sucursal
            kilos_por_cliente[sucursal_norm] += peso_cobrable
        else:
            # Es un cliente OTROS
            kilos_otros_detalle[cliente] += peso_cobrable
    
    # Calcular total de kilos y porcentajes agrupados
    total_kilos = sum(kilos_por_cliente.values()) + sum(kilos_otros_detalle.values())
    porcentajes_kilos = []
    
    # Agregar sucursales con kilos
    for sucursal, kilos in sorted(kilos_por_cliente.items(), key=lambda x: x[1], reverse=True):
        if kilos > 0:
            porcentaje = (float(kilos) / float(total_kilos) * 100) if total_kilos > 0 else 0
            porcentajes_kilos.append({
                'cliente': sucursal,
                'kilos_volumetricos': float(kilos),
                'porcentaje': round(porcentaje, 2)
            })
    
    # Agregar OTROS (suma de todos los clientes no sucursales)
    total_otros_kilos = sum(kilos_otros_detalle.values())
    if total_otros_kilos > 0:
        porcentaje_otros = (float(total_otros_kilos) / float(total_kilos) * 100) if total_kilos > 0 else 0
        porcentajes_kilos.append({
            'cliente': 'OTROS',
            'kilos_volumetricos': float(total_otros_kilos),
            'porcentaje': round(porcentaje_otros, 2)
        })
    
    # Agregar clientes sin medidas (para información)
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
    # Desde que solicitud cambió a 'en_despacho' hasta fecha_embalaje del bulto
    # Usamos fecha_creacion del bulto como proxy de cuando cambió a en_despacho
    bultos_embalados = Bulto.objects.filter(
        solicitud__in=solicitudes_base,
        fecha_embalaje__isnull=False,
        estado='listo_despacho'
    ).select_related('solicitud')
    
    if transporte_filtro:
        bultos_embalados = bultos_embalados.filter(
            Q(transportista=transporte_filtro) | 
            Q(transportista_extra=transporte_filtro) |
            Q(solicitud__transporte=transporte_filtro)
        )
    
    lead_times_emb = []
    for bulto in bultos_embalados:
        if bulto.fecha_embalaje and bulto.fecha_creacion:
            delta = bulto.fecha_embalaje - bulto.fecha_creacion
            lead_times_emb.append(delta.total_seconds() / 3600)  # En horas
    
    lt_emb_promedio = sum(lead_times_emb) / len(lead_times_emb) if lead_times_emb else 0
    lt_emb_min = min(lead_times_emb) if lead_times_emb else 0
    lt_emb_max = max(lead_times_emb) if lead_times_emb else 0
    
    # 3. LEAD TIME TOTAL (SOLICITUD COMPLETA)
    # Desde created_at de solicitud hasta fecha_envio/fecha_entrega cuando bulto está finalizado
    # Solo usamos bultos con estado='finalizado' porque cuando la solicitud pasa a 'despachado',
    # todos sus bultos se finalizan automáticamente
    bultos_finalizados = Bulto.objects.filter(
        solicitud__in=solicitudes_base,
        estado='finalizado',  # Solo bultos finalizados (cuando solicitud está despachada)
        fecha_envio__isnull=False  # Debe tener fecha_envio (establecida al finalizar)
    ).select_related('solicitud')
    
    if transporte_filtro:
        bultos_finalizados = bultos_finalizados.filter(
            Q(transportista=transporte_filtro) | 
            Q(transportista_extra=transporte_filtro) |
            Q(solicitud__transporte=transporte_filtro)
        )
    
    lead_times_total = []
    for bulto in bultos_finalizados:
        # Usar fecha_envio (prioridad) o fecha_entrega como fecha final
        # fecha_envio se establece cuando el admin finaliza el bulto al marcar solicitud como despachada
        fecha_fin = bulto.fecha_envio or bulto.fecha_entrega
        if fecha_fin and bulto.solicitud.created_at:
            delta = fecha_fin - bulto.solicitud.created_at
            lead_times_total.append(delta.total_seconds() / 3600)  # En horas
    
    lt_total_promedio = sum(lead_times_total) / len(lead_times_total) if lead_times_total else 0
    lt_total_min = min(lead_times_total) if lead_times_total else 0
    lt_total_max = max(lead_times_total) if lead_times_total else 0
    
    # 4. CÓDIGOS EN DESPACHO (con días y valorización)
    # Bultos con estado 'listo_despacho' pero sin fecha_envio
    # OPTIMIZADO: Usar prefetch_related para evitar N+1 queries
    from django.db.models import Prefetch
    
    bultos_en_despacho = Bulto.objects.filter(
        estado='listo_despacho',
        fecha_envio__isnull=True,
        fecha_embalaje__isnull=False
    ).select_related('solicitud').prefetch_related(
        Prefetch(
            'detalles',  # related_name en SolicitudDetalle.bulto
            queryset=SolicitudDetalle.objects.all(),
            to_attr='detalles_precargados'
        )
    )
    
    if transporte_filtro:
        bultos_en_despacho = bultos_en_despacho.filter(
            Q(transportista=transporte_filtro) | 
            Q(transportista_extra=transporte_filtro) |
            Q(solicitud__transporte=transporte_filtro)
        )
    
    # Agrupar por transporte y calcular métricas
    solicitudes_por_transporte = {}
    
    # Primero, recopilar todos los códigos únicos para hacer batch query de precios
    todos_codigos = set()
    detalles_por_bulto = {}
    
    for bulto in bultos_en_despacho:
        # Usar los detalles precargados
        detalles = getattr(bulto, 'detalles_precargados', [])
        if not detalles:
            # Fallback: usar el método relacionado si prefetch no funcionó
            detalles = list(bulto.detalles.all())
        
        detalles_por_bulto[bulto.id] = (bulto, detalles)
        
        for detalle in detalles:
            todos_codigos.add(detalle.codigo)
    
    # OPTIMIZADO: Batch query para obtener todos los precios de una vez
    precios_cache = {}
    if todos_codigos:
        stocks = Stock.objects.filter(codigo__in=todos_codigos).values('codigo', 'precio')
        for stock in stocks:
            # Si hay múltiples stocks para el mismo código, tomar el primero con precio válido
            if stock['codigo'] not in precios_cache and stock.get('precio'):
                precios_cache[stock['codigo']] = stock['precio']
    
    # Ahora procesar los bultos con datos precargados
    for bulto, detalles in detalles_por_bulto.values():
        # Determinar transporte (prioridad: transportista_extra > transportista > solicitud.transporte)
        transporte_slug = bulto.transportista_extra or bulto.transportista or bulto.solicitud.transporte or 'Sin transporte'
        # Obtener nombre legible del transporte usando la configuración
        transporte = TransporteConfig.etiqueta(transporte_slug) if transporte_slug != 'Sin transporte' else 'Sin transporte'
        
        if transporte not in solicitudes_por_transporte:
            solicitudes_por_transporte[transporte] = {
                'solicitudes': set(),
                'horas_laborales': [],
                'dias_calendario': [],
                'valor_usd': Decimal('0.00')
            }
        
        # Agregar la solicitud única (no por cada detalle)
        solicitudes_por_transporte[transporte]['solicitudes'].add(bulto.solicitud.id)
        
        # Calcular horas laborales y días calendario desde fecha_embalaje
        if bulto.fecha_embalaje:
            # Horas laborales (excluyendo fines de semana, 8h/día)
            horas_lab = calcular_horas_laborales(bulto.fecha_embalaje, ahora)
            solicitudes_por_transporte[transporte]['horas_laborales'].append(horas_lab)
            
            # Días calendario (para referencia)
            dias_cal = (ahora - bulto.fecha_embalaje).total_seconds() / 86400
            solicitudes_por_transporte[transporte]['dias_calendario'].append(dias_cal)
        
        # Valorizar todos los detalles del bulto
        for detalle in detalles:
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
    transportes_disponibles.sort()
    
    result = {
        'lead_time_preparacion': {
            'promedio_horas': lt_prep_promedio,
            'promedio_dias': lt_prep_promedio / 24,
            'min_horas': lt_prep_min,
            'min_dias': lt_prep_min / 24,
            'max_horas': lt_prep_max,
            'max_dias': lt_prep_max / 24,
            'total_registros': len(lead_times_prep),
            'tendencia_diaria': tendencia_diaria_prep,
            'tendencia_diaria_json': tendencia_diaria_json
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
        'solicitudes_en_despacho': solicitudes_despacho,
        'transportes_disponibles': transportes_disponibles,
        'periodo_dias': periodo_dias,
        # Estadísticas por cliente (agrupadas: sucursales + OTROS)
        'porcentajes_operaciones_cliente': porcentajes_operaciones,
        'porcentajes_kilos_cliente': porcentajes_kilos,
        # Desglose detallado de OTROS
        'porcentajes_operaciones_otros': operaciones_otros,
        'porcentajes_kilos_otros': porcentajes_otros_detalle_kilos
    }
    
    # Guardar en caché por 5 minutos (300 segundos)
    cache.set(cache_key, result, timeout=300)
    
    return result
