from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from core.decorators import role_required
from solicitudes.models import Solicitud, SolicitudDetalle
from bodega.models import Stock


@login_required
@role_required(['admin'])
def emision_guias(request):
    """
    Vista para emisión de guías SAP.
    Permite seleccionar solicitudes y generar detalle en texto plano para copiar.
    """
    # Filtrar solicitudes que están listas para emitir guía
    # Estados: embalado, listo_despacho, en_despacho (ya preparadas y embaladas)
    estados_para_guia = ['embalado', 'listo_despacho', 'en_despacho']
    
    # Búsqueda y filtros
    q = request.GET.get('q', '').strip()
    estado_filtro = request.GET.get('estado', '')
    cliente_filtro = request.GET.get('cliente', '').strip()
    
    solicitudes = Solicitud.objects.filter(
        estado__in=estados_para_guia
    ).select_related('solicitante').prefetch_related(
        Prefetch(
            'detalles',
            queryset=SolicitudDetalle.objects.select_related('bulto').order_by('id')
        )
    ).order_by('-fecha_solicitud', '-hora_solicitud')
    
    # Aplicar filtros
    if q:
        solicitudes = solicitudes.filter(
            Q(numero_pedido__icontains=q) |
            Q(numero_st__icontains=q) |
            Q(numero_ot__icontains=q) |
            Q(cliente__icontains=q) |
            Q(id__icontains=q)
        )
    
    if estado_filtro:
        solicitudes = solicitudes.filter(estado=estado_filtro)
    
    if cliente_filtro:
        solicitudes = solicitudes.filter(cliente__icontains=cliente_filtro)
    
    # Obtener lista de clientes únicos para el dropdown
    clientes = Solicitud.objects.filter(
        estado__in=estados_para_guia
    ).values_list('cliente', flat=True).distinct().order_by('cliente')
    
    # Obtener estados únicos
    estados_disponibles = Solicitud.objects.filter(
        estado__in=estados_para_guia
    ).values_list('estado', flat=True).distinct()
    
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(solicitudes, 50)  # 50 por página
    page = request.GET.get('page', 1)
    try:
        solicitudes_paginadas = paginator.page(page)
    except:
        solicitudes_paginadas = paginator.page(1)
    
    context = {
        'solicitudes': solicitudes_paginadas,
        'clientes': clientes,
        'estados_disponibles': estados_disponibles,
        'q': q,
        'estado_filtro': estado_filtro,
        'cliente_filtro': cliente_filtro,
    }
    
    return render(request, 'guias/emision.html', context)


@login_required
@role_required(['admin'])
def generar_detalle_guia(request):
    """
    Genera el detalle de guía en texto plano para las solicitudes seleccionadas.
    Recibe IDs de solicitudes y retorna texto formateado con: Código, Descripción, Cantidad, Proyecto (OC/OF/PC/ST).
    Las guías NO van valorizadas (sin precios), solo detalle de códigos y proyectos asociados.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Método no permitido'}, status=405)
        
        solicitud_ids = request.POST.getlist('solicitud_ids[]')
        
        if not solicitud_ids:
            return JsonResponse({'error': 'No se seleccionaron solicitudes'}, status=400)
        
        try:
            # Convertir a enteros
            solicitud_ids = [int(id) for id in solicitud_ids]
        except ValueError as e:
            logger.error(f"Error al convertir IDs: {e}")
            return JsonResponse({'error': 'IDs inválidos'}, status=400)
        
        # Obtener solicitudes con sus detalles (sin filtrar por estado para permitir más flexibilidad)
        solicitudes = Solicitud.objects.filter(
            id__in=solicitud_ids
        ).prefetch_related(
            Prefetch(
                'detalles',
                queryset=SolicitudDetalle.objects.order_by('id')
            )
        ).order_by('id')
        
        if not solicitudes.exists():
            return JsonResponse({'error': 'No se encontraron solicitudes válidas'}, status=404)
    
        # Generar texto plano — formato compacto tipo guía de despacho
        # Columnas: CODIGO(14) DESCRIPCION(36) CANT(5) P.UNIT(10) PROYECTO(15)
        SEP = "-" * 85
        PRECIO_DEFAULT = "$10.000"

        lineas = []
        lineas.append(SEP)
        lineas.append(f"{'PROYECTO':<15} {'CODIGO':<14} {'DESCRIPCION':<36} {'CANT':>5} {'P.UNITARIA':>10}")
        lineas.append(SEP)

        total_productos = 0

        # Detalles de cada solicitud
        for solicitud in solicitudes:
            # Determinar proyecto asociado según el tipo de solicitud
            tipo_solicitud = solicitud.tipo or ''
            proyecto = ''

            if tipo_solicitud == 'PC':
                proyecto = solicitud.numero_pedido or f"PC-{solicitud.id}"
            elif tipo_solicitud == 'OC':
                proyecto = solicitud.numero_pedido or f"OC-{solicitud.id}"
            elif tipo_solicitud == 'OF':
                proyecto = solicitud.numero_pedido or solicitud.numero_ot or f"OF-{solicitud.id}"
            elif tipo_solicitud == 'ST':
                proyecto = solicitud.numero_st or f"ST{solicitud.id}"
            elif tipo_solicitud == 'EM':
                proyecto = solicitud.numero_pedido or f"EM-{solicitud.id}"
            elif tipo_solicitud == 'RM':
                proyecto = solicitud.numero_pedido or f"RM-{solicitud.id}"
            else:
                proyecto = solicitud.numero_pedido or solicitud.numero_st or f"SOL-{solicitud.id}"

            # Detalles de productos
            for detalle in solicitud.detalles.all():
                codigo = (detalle.codigo or '').strip()[:14]
                descripcion = (detalle.descripcion or '').strip()
                cantidad = str(detalle.cantidad)

                # Descripción larga: primera línea con todos los campos, resto solo descripción
                max_desc = 36
                if len(descripcion) > max_desc:
                    lineas.append(f"{proyecto:<15} {codigo:<14} {descripcion[:max_desc]:<36} {cantidad:>5} {PRECIO_DEFAULT:>10}")
                    resto = descripcion[max_desc:]
                    while resto:
                        lineas.append(f"{'':15} {'':14}   {resto[:max_desc]}")
                        resto = resto[max_desc:]
                else:
                    lineas.append(f"{proyecto:<15} {codigo:<14} {descripcion:<36} {cantidad:>5} {PRECIO_DEFAULT:>10}")

                total_productos += 1

            # Separador entre solicitudes (solo si hay más de una)
            if solicitudes.count() > 1:
                lineas.append(SEP)


        # Pie compacto
        lineas.append(SEP)
        lineas.append(f"Total: {solicitudes.count()} solicitud(es) | {total_productos} producto(s)")

        texto_plano = "\n".join(lineas)

        
        return JsonResponse({
            'success': True,
            'texto': texto_plano,
            'total_solicitudes': solicitudes.count(),
            'total_productos': total_productos,
            'solicitud_ids': [s.id for s in solicitudes]
        })
    
    except Exception as e:
        logger.error(f"Error al generar detalle de guía: {e}", exc_info=True)
        return JsonResponse({
            'error': f'Error al generar el detalle: {str(e)}'
        }, status=500)
