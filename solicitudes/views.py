from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
import json

from core.decorators import role_required
from core.models import Bodega
from configuracion.models import EstadoWorkflow
from .forms import SolicitudForm, SolicitudDetalleFormSet, SolicitudEdicionAdminForm
from .models import Solicitud
from .services import crear_solicitud_desde_payload, SolicitudServiceError


@login_required
def lista_solicitudes(request):
    """
    Vista principal del módulo de solicitudes.
    Aplica filtros según rol y parámetros del usuario.
    """
    user = request.user
    
    # Importaciones necesarias
    from django.db.models import Prefetch, Exists, OuterRef
    from despacho.models import Bulto
    from solicitudes.models import SolicitudDetalle
    from configuracion.models import EstadoWorkflow, TransporteConfig
    
    # Pre-cargar caché de configuraciones (evita 60+ queries)
    EstadoWorkflow._cargar_cache()
    TransporteConfig._cargar_cache()
    
    # PASO 1: Crear queryset base
    solicitudes = Solicitud.objects.all()

    # PASO 2: Aplicar filtros por rol (OPTIMIZADO: usa Exists en lugar de JOIN + distinct)
    if user.es_bodega():
        bodegas_usuario = user.get_bodegas_codigos()
        # Optimización: usar Exists en lugar de JOIN + distinct (mucho más rápido)
        detalles_pendientes = SolicitudDetalle.objects.filter(
            solicitud=OuterRef('pk'),
            bodega__in=bodegas_usuario,
            estado_bodega='pendiente'
        )
        solicitudes = solicitudes.annotate(
            tiene_pendientes=Exists(detalles_pendientes)
        ).filter(tiene_pendientes=True)
    elif user.es_despacho():
        solicitudes = solicitudes.filter(estado__in=['en_despacho', 'embalado', 'listo_despacho', 'en_ruta'])

    # PASO 3: Aplicar filtros desde la URL
    estado = (request.GET.get('estado', '') or '').strip()
    tipo = request.GET.get('tipo', '')
    urgente = request.GET.get('urgente', '')
    busqueda = request.GET.get('q', '')

    if estado:
        solicitudes = solicitudes.filter(estado=estado)
    if tipo:
        solicitudes = solicitudes.filter(tipo=tipo)
    if urgente == '1':
        solicitudes = solicitudes.filter(urgente=True)
    if busqueda:
        solicitudes = solicitudes.filter(
            Q(cliente__icontains=busqueda)
            | Q(codigo__icontains=busqueda)
            | Q(descripcion__icontains=busqueda)
            | Q(numero_pedido__icontains=busqueda)
            | Q(numero_st__icontains=busqueda)
            | Q(numero_ot__icontains=busqueda)
        )

    # PASO 4: Cargar relaciones ANTES de paginar (Django solo carga 25 en la query)
    # El prefetch_related es inteligente y solo carga relaciones de los objetos obtenidos
    solicitudes = (
        solicitudes
        .select_related('solicitante')  # ForeignKey: siempre eficiente
        .prefetch_related(
            # Solo prefetch de bultos (el template no usa detalles en la lista)
            Prefetch('bultos', queryset=Bulto.objects.only('id', 'codigo'))
        )
        .order_by('id')
    )
    
    # PASO 5: Paginar (esto ejecuta la query pero Django solo trae 25 registros)
    paginator = Paginator(solicitudes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Stats: Solo si es necesario (comentado por ahora para velocidad)
    # stats = Solicitud.objects.values('estado').annotate(total=Count('id'))
    stats = []  # Desactivado temporalmente para mejorar velocidad

    estados_opciones = EstadoWorkflow.activos_para(EstadoWorkflow.TIPO_SOLICITUD)

    context = {
        'page_obj': page_obj,
        'estado': estado,
        'tipo': tipo,
        'urgente': urgente,
        'busqueda': busqueda,
        'stats': stats,
        'es_admin': user.es_admin(),
        'tipos': Solicitud.TIPOS,
        'estados_config': estados_opciones,
    }
    return render(request, 'solicitudes/lista.html', context)


@login_required
@role_required(['admin'])
def crear_solicitud(request):
    """
    Permite al admin registrar nuevas solicitudes.
    """
    bodegas_activas = list(
        Bodega.objects.filter(activa=True)
        .order_by('codigo')
        .values_list('codigo', 'nombre')
    )
    bodegas_usuario = request.user.get_bodegas_codigos() if hasattr(request.user, "get_bodegas_codigos") else []
    default_bodega = bodegas_usuario[0] if bodegas_usuario else (bodegas_activas[0][0] if bodegas_activas else '')
    form_kwargs = {
        'available_bodegas': bodegas_activas,
        'default_bodega': default_bodega,
    }
    
    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        formset = SolicitudDetalleFormSet(request.POST, prefix='detalles', form_kwargs=form_kwargs)
        if form.is_valid() and formset.is_valid():
            # Filtrar detalles realmente ingresados
            detalles_validos = []
            for f in formset:
                cd = f.cleaned_data if f.is_valid() else {}
                if cd.get('DELETE'):
                    continue
                codigo = cd.get('codigo')
                descripcion = cd.get('descripcion')
                cantidad = cd.get('cantidad')
                if not codigo and not descripcion and not cantidad:
                    continue
                if not cantidad or cantidad <= 0:
                    continue
                detalles_validos.append(cd)

            if not detalles_validos:
                messages.error(request, 'Debes ingresar al menos un producto en la tabla.')
            else:
                # Crear la solicitud (cabecera)
                solicitud = form.save(commit=False)
                solicitud.solicitante = request.user

                # Tomar la primera línea como resumen para cabecera
                primera = detalles_validos[0]
                solicitud.codigo = primera.get('codigo') or 'SC'
                solicitud.descripcion = primera.get('descripcion') or ''
                solicitud.cantidad_solicitada = primera.get('cantidad')

                solicitud.save()

                # Guardar todas las líneas en SolicitudDetalle
                for cd in detalles_validos:
                    solicitud.detalles.create(
                        codigo=cd.get('codigo') or 'SC',
                        descripcion=cd.get('descripcion') or '',
                        cantidad=cd.get('cantidad'),
                        bodega=cd.get('bodega') or '',
                    )

                messages.success(request, f'Solicitud #{solicitud.id} creada correctamente.')
                return redirect('solicitudes:lista')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = SolicitudForm()
        formset = SolicitudDetalleFormSet(prefix='detalles', form_kwargs=form_kwargs)

    return render(request, 'solicitudes/formulario.html', {'form': form, 'formset': formset})


@login_required
def detalle_solicitud(request, pk):
    """
    Muestra el detalle de una solicitud.
    Todos los roles pueden verla si tienen acceso a la lista.
    """
    solicitud = get_object_or_404(Solicitud.objects.select_related('solicitante'), pk=pk)

    # Validación de acceso similar a la lista
    if request.user.es_bodega() and solicitud.estado != 'pendiente':
        messages.warning(request, 'No puedes acceder a solicitudes fuera de tu módulo.')
        return redirect('solicitudes:lista')
    if request.user.es_despacho() and solicitud.estado not in ['en_despacho', 'embalado', 'listo_despacho', 'en_ruta']:
        messages.warning(request, 'No puedes acceder a solicitudes fuera de tu módulo.')
        return redirect('solicitudes:lista')

    detalles = solicitud.detalles.all()
    
    # Filtrar detalles si es usuario de bodega
    if request.user.es_bodega():
        bodegas_usuario = request.user.get_bodegas_codigos()
        detalles = detalles.filter(bodega__in=bodegas_usuario)
        
    return render(request, 'solicitudes/detalle.html', {'solicitud': solicitud, 'detalles': detalles})


@login_required
def preparar_producto(request, detalle_id):
    """
    Marca un producto específico como preparado por el usuario de bodega.
    """
    from django.utils import timezone
    from .models import SolicitudDetalle
    
    detalle = get_object_or_404(SolicitudDetalle, pk=detalle_id)
    
    # Verificar permisos
    if not request.user.puede_gestionar_bodega(detalle.bodega):
        messages.error(request, 'No tienes permiso para gestionar esta bodega.')
        return redirect('solicitudes:detalle', pk=detalle.solicitud.id)
        
    if request.method == 'POST':
        detalle.estado_bodega = 'preparado'
        detalle.preparado_por = request.user
        detalle.fecha_preparacion = timezone.now()
        detalle.save()
        
        messages.success(request, f'Producto {detalle.codigo} marcado como preparado.')
        
        # Verificar si la solicitud está completa
        solicitud = detalle.solicitud
        pendientes = solicitud.detalles.exclude(estado_bodega='preparado').exists()
        
        if not pendientes:
            solicitud.estado = 'en_despacho'
            solicitud.save()
            messages.info(request, '¡Todos los productos preparados! Solicitud enviada a despacho.')
            
    return redirect('solicitudes:detalle', pk=detalle.solicitud.id)


@login_required
def detalle_solicitud_ajax(request, pk):
    """
    Endpoint AJAX para obtener el detalle de una solicitud en formato JSON.
    Usado por el modal de vista rápida.
    """
    try:
        solicitud = Solicitud.objects.select_related('solicitante').prefetch_related('detalles__bulto', 'bultos__detalles').get(pk=pk)
        
        # Validación de acceso
        if request.user.es_bodega() and solicitud.estado != 'pendiente':
            return JsonResponse({'error': 'No tienes acceso a esta solicitud'}, status=403)
        if request.user.es_despacho() and solicitud.estado not in ['en_despacho', 'embalado', 'listo_despacho', 'en_ruta']:
            return JsonResponse({'error': 'No tienes acceso a esta solicitud'}, status=403)
        
        # Preparar datos de productos con información de bultos
        productos = []
        detalles = solicitud.detalles.all()
        
        if detalles.exists():
            # Solicitud nueva con tabla de detalles
            for det in detalles:
                productos.append({
                    'codigo': det.codigo,
                    'descripcion': det.descripcion,
                    'cantidad': det.cantidad,
                    'bulto_id': det.bulto_id,
                    'bulto_codigo': det.bulto.codigo if det.bulto else None,
                    'estado_bodega': det.get_estado_bodega_display()
                })
        else:
            # Solicitud antigua sin detalles
            productos.append({
                'codigo': solicitud.codigo,
                'descripcion': solicitud.descripcion,
                'cantidad': solicitud.cantidad_solicitada,
                'bulto_id': None,
                'bulto_codigo': None,
                'estado_bodega': 'N/A'
            })
        
        # Preparar datos de bultos
        bultos_data = []
        for bulto in solicitud.bultos.all():
            codigos_en_bulto = [det.codigo for det in bulto.detalles.all()]
            bultos_data.append({
                'id': bulto.id,
                'codigo': bulto.codigo,
                'estado': bulto.get_estado_display(),
                'tipo': bulto.get_tipo_display(),
                'transportista': bulto.get_transportista_display(),
                'peso': float(bulto.peso_total),
                'largo': float(bulto.largo_cm),
                'ancho': float(bulto.ancho_cm),
                'alto': float(bulto.alto_cm),
                'volumen': bulto.volumen_m3,
                'codigos': codigos_en_bulto,
                'fecha_creacion': bulto.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            })
        
        # Preparar respuesta
        data = {
            'id': solicitud.id,
            'fecha': solicitud.fecha_solicitud.strftime('%d/%m/%Y'),
            'hora': solicitud.hora_solicitud.strftime('%H:%M'),
            'tipo': solicitud.get_tipo_display(),
            'numero_pedido': solicitud.numero_pedido or '-',
            'numero_st': solicitud.numero_st or '-',
            'numero_ot': solicitud.numero_ot or '-',
            'numero_guia_despacho': solicitud.numero_guia_despacho or '',
            'cliente': solicitud.cliente,
            'bodega': solicitud.bodega or '-',
            'transporte': solicitud.get_transporte_display(),
            'estado': solicitud.get_estado_display(),
            'color_estado': solicitud.color_estado(),
            'urgente': solicitud.urgente,
            'afecta_stock': solicitud.afecta_stock,
            'descripcion': solicitud.descripcion or '-',
            'observacion': solicitud.observacion or 'Sin observaciones',
            'solicitante': solicitud.solicitante.nombre_completo if solicitud.solicitante and solicitud.solicitante.nombre_completo else (solicitud.solicitante.username if solicitud.solicitante else 'Sistema'),
            'created_at': solicitud.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': solicitud.updated_at.strftime('%d/%m/%Y %H:%M'),
            'productos': productos,
            'bultos': bultos_data
        }
        
        return JsonResponse(data)
        
    except Solicitud.DoesNotExist:
        return JsonResponse({'error': 'Solicitud no encontrada'}, status=404)



# ========================
# API para IA / MCP
# ========================

@csrf_exempt
def api_crear_solicitud_ia(request: HttpRequest) -> HttpResponse:
    """
    Endpoint simple para que un agente de IA (MCP, Gemini, etc.) cree solicitudes.

    - Método: POST
    - Content-Type: application/json
    - Autenticación: cabecera X-API-TOKEN debe coincidir con settings.IA_API_TOKEN si está definido.

    El cuerpo debe respetar el formato aceptado por crear_solicitud_desde_payload.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Método no permitido"}, status=405)

    api_token_conf = getattr(settings, "IA_API_TOKEN", "")
    api_token_req = request.headers.get("X-API-TOKEN") or request.headers.get("Authorization", "").replace("Bearer ", "")

    if api_token_conf and api_token_req != api_token_conf:
        return JsonResponse({"detail": "No autorizado"}, status=403)

    try:
        body = request.body.decode("utf-8") or "{}"
        data = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON inválido"}, status=400)

    solicitante = request.user if request.user.is_authenticated else None

    try:
        solicitud = crear_solicitud_desde_payload(data, solicitante=solicitante)
    except SolicitudServiceError as e:
        return JsonResponse({"detail": str(e)}, status=400)
    except Exception as e:
        # Error inesperado - preferible registrar en logs reales
        return JsonResponse({"detail": f"Error interno: {e}"}, status=500)

    response = {
        "id": solicitud.id,
        "tipo": solicitud.tipo,
        "numero_pedido": solicitud.numero_pedido,
        "numero_ot": solicitud.numero_ot,
        "numero_st": solicitud.numero_st,
        "cliente": solicitud.cliente,
        "bodega": solicitud.bodega,
        "transporte": solicitud.get_transporte_display(),
        "estado": solicitud.estado,
        "urgente": solicitud.urgente,
        "created_at": solicitud.created_at.isoformat(),
    }
    return JsonResponse(response, status=201)


# ========================
# Vistas de edición para Admin
# ========================

@login_required
@role_required(['admin'])
def editar_solicitud(request, pk):
    """
    Permite al admin editar cualquier aspecto de la solicitud.
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    if request.method == 'POST':
        form = SolicitudEdicionAdminForm(request.POST, instance=solicitud)
        formset = SolicitudDetalleFormSet(request.POST, instance=solicitud)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Solicitud #{solicitud.id} actualizada correctamente.')
            return redirect('solicitudes:detalle', pk=solicitud.pk)
    else:
        form = SolicitudEdicionAdminForm(instance=solicitud)
        formset = SolicitudDetalleFormSet(instance=solicitud)
    
    bodegas_activas = Bodega.objects.filter(activa=True).order_by('codigo')
    
    context = {
        'form': form,
        'formset': formset,
        'solicitud': solicitud,
        'bodegas': bodegas_activas,
        'es_edicion': True,
    }
    return render(request, 'solicitudes/formulario.html', context)


@login_required
@role_required(['admin'])
def cambiar_estado_solicitud(request, pk):
    """
    Permite al admin cambiar el estado de una solicitud.
    Si el nuevo estado es 'despachado', descuenta el stock.
    """
    from .services import descontar_stock_despachado
    import logging
    
    logger = logging.getLogger(__name__)
    
    # LOG INICIAL
    print(f"\n{'='*60}")
    print(f"🔔 CAMBIAR ESTADO SOLICITUD - Solicitud #{pk}")
    print(f"{'='*60}")
    print(f"Usuario: {request.user}")
    print(f"Método: {request.method}")
    print(f"POST data: {dict(request.POST)}")
    
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    print(f"Estado actual: {solicitud.estado}")
    print(f"Afecta stock: {solicitud.afecta_stock}")
    
    if request.method != 'POST':
        print("❌ Método no es POST")
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    nuevo_estado = request.POST.get('estado')
    numero_guia_despacho = request.POST.get('numero_guia_despacho', '').strip()
    
    print(f"Nuevo estado: {nuevo_estado}")
    print(f"Número guía: {numero_guia_despacho}")
    
    logger.info(f"Cambiar estado solicitud #{solicitud.id}: {solicitud.estado} → {nuevo_estado}")
    logger.info(f"Guía: {numero_guia_despacho}")
    
    if not nuevo_estado:
        return JsonResponse({'success': False, 'message': 'Estado no proporcionado'}, status=400)
    
    estado_anterior = solicitud.estado
    solicitud.estado = nuevo_estado
    
    # Si se proporciona número de guía, guardarlo
    if numero_guia_despacho:
        solicitud.numero_guia_despacho = numero_guia_despacho
        solicitud.save(update_fields=['estado', 'numero_guia_despacho'])
    else:
        solicitud.save(update_fields=['estado'])
    
    # Si el nuevo estado es despachado, descontar stock
    resultado_descuento = None
    if nuevo_estado == 'despachado' and estado_anterior != 'despachado':
        logger.info(f"Ejecutando descuento de stock para solicitud #{solicitud.id}")
        resultado_descuento = descontar_stock_despachado(solicitud)
        logger.info(f"Resultado descuento: {resultado_descuento}")
        
        if not resultado_descuento['success']:
            mensaje = f'Solicitud marcada como despachada, pero hubo errores al descontar stock: {resultado_descuento.get("errores", [])}'
            return JsonResponse({
                'success': True,
                'warning': True,
                'message': mensaje,
                'descuento': resultado_descuento
            })
    elif nuevo_estado == 'despachado' and estado_anterior == 'despachado':
        logger.info(f"Solicitud #{solicitud.id} ya estaba despachada, no se descuenta nuevamente")
    
    mensaje = f'Estado cambiado a {solicitud.get_estado_display()}'
    if numero_guia_despacho:
        mensaje += f' (Guía/Factura: {numero_guia_despacho})'
    if resultado_descuento and resultado_descuento['descontados'] > 0:
        mensaje += f'. Se descontaron {resultado_descuento["descontados"]} productos de bodega 013.'
    elif nuevo_estado == 'despachado' and not resultado_descuento:
        mensaje += ' (Ya estaba despachada, sin cambios en stock)'
    
    print(f"\n✅ CAMBIO EXITOSO:")
    print(f"   Estado: {estado_anterior} → {nuevo_estado}")
    print(f"   Mensaje: {mensaje}")
    print(f"{'='*60}\n")
    
    return JsonResponse({
        'success': True,
        'message': mensaje,
        'nuevo_estado': nuevo_estado,
        'nuevo_estado_display': solicitud.get_estado_display(),
        'color_estado': solicitud.color_estado(),
        'descuento': resultado_descuento
    })


@login_required
@role_required(['admin'])
def cambiar_afecta_stock(request, pk):
    """
    Permite al admin cambiar el flag afecta_stock de una solicitud.
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    afecta_stock = request.POST.get('afecta_stock') == 'true'
    solicitud.afecta_stock = afecta_stock
    solicitud.save(update_fields=['afecta_stock'])
    
    mensaje = 'La solicitud ahora {} stock.'.format('afecta' if afecta_stock else 'NO afecta')
    
    return JsonResponse({
        'success': True,
        'message': mensaje,
        'afecta_stock': afecta_stock
    })


@login_required
def buscar_codigo_stock(request):
    """
    API para buscar un código en Stock y retornar su información.
    """
    from bodega.models import Stock
    
    codigo = request.GET.get('codigo', '').strip()
    
    if not codigo:
        return JsonResponse({'success': False, 'message': 'Código no proporcionado'}, status=400)
    
    # Buscar el código en Stock
    stocks = Stock.objects.filter(codigo=codigo)
    
    if not stocks.exists():
        return JsonResponse({
            'success': False,
            'message': f'El código {codigo} no existe en el sistema de stock'
        })
    
    # Obtener información del código
    primer_stock = stocks.first()
    descripcion = primer_stock.descripcion or ''
    
    # Agrupar por bodega con stock disponible
    bodegas_disponibles = []
    for stock in stocks:
        if stock.stock_disponible > 0:
            bodegas_disponibles.append({
                'codigo_bodega': stock.bodega,
                'nombre_bodega': stock.bodega_nombre or stock.bodega,
                'stock_disponible': float(stock.stock_disponible)
            })
    
    return JsonResponse({
        'success': True,
        'codigo': codigo,
        'descripcion': descripcion,
        'bodegas': bodegas_disponibles,
        'tiene_stock': len(bodegas_disponibles) > 0
    })