import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse

from core.decorators import role_required
from core.models import Bodega
from solicitudes.models import SolicitudDetalle, Solicitud

from .forms import TransferenciaForm
from .models import BodegaTransferencia, CargaStock, Stock, StockReserva
from .services import procesar_archivo_stock


def mover_stock(codigo, bodega_origen, cantidad, solicitud=None):
    """
    Ajusta el stock espejo moviendo unidades desde la bodega origen a 013.
    Si la solicitud tiene afecta_stock=False, no realiza ningún movimiento.
    """
    # Si se proporciona solicitud y no afecta stock, no hacer nada
    if solicitud and not solicitud.afecta_stock:
        return
    
    if not bodega_origen:
        return

    origen = Stock.objects.filter(codigo=codigo, bodega=bodega_origen).first()
    descripcion = ''
    cod_grupo = None
    descripcion_grupo = ''
    if origen:
        descripcion = origen.descripcion or ''
        cod_grupo = origen.cod_grupo
        descripcion_grupo = origen.descripcion_grupo or ''
        origen.stock_disponible = max(0, (origen.stock_disponible or 0) - cantidad)
        origen.save(update_fields=['stock_disponible'])

    destino_defaults = {
        'descripcion': descripcion,
        'cod_grupo': cod_grupo,
        'descripcion_grupo': descripcion_grupo,
        'bodega_nombre': 'Despacho 013',
        'ubicacion': '',
        'ubicacion_2': '',
        'stock_disponible': 0,
    }
    destino, created = Stock.objects.get_or_create(
        codigo=codigo,
        bodega='013',
        defaults=destino_defaults
    )
    destino.stock_disponible = (destino.stock_disponible or 0) + cantidad
    destino.save(update_fields=['stock_disponible'])


def resolver_bodega_origen(detalle, valor_post=None):
    if valor_post:
        return valor_post
    if detalle.bodega:
        return detalle.bodega
    stock = Stock.objects.filter(codigo=detalle.codigo).order_by('-stock_disponible').first()
    return stock.bodega if stock else ''

@login_required
@role_required(['admin'])
def cargar_stock(request):
    """
    Vista para que el admin suba el archivo de stock diario.
    """
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, "Debes seleccionar un archivo.")
            return redirect('bodega:cargar_stock')
            
        if not archivo.name.endswith(('.xls', '.xlsx')):
            messages.error(request, "Formato no válido. Usa Excel (.xlsx, .xls)")
            return redirect('bodega:cargar_stock')
            
        try:
            resultado = procesar_archivo_stock(archivo, request.user)
            messages.success(
                request, 
                f"✅ Stock cargado correctamente. "
                f"Productos: {resultado['total_productos']}, "
                f"Bodegas: {resultado['total_bodegas']}"
            )
            if resultado.get('errores_fila', 0) > 0:
                messages.warning(request, f"⚠️ Hubo {resultado['errores_fila']} filas con errores que se omitieron.")
                
            return redirect('bodega:historial_cargas')
        except Exception as e:
            messages.error(request, f"❌ Error al procesar archivo: {e}")
            
    # Mostrar última carga activa
    ultima_carga = CargaStock.objects.filter(estado='activo').first()
    
    return render(request, 'bodega/cargar_stock.html', {
        'ultima_carga': ultima_carga
    })

@login_required
def consultar_stock(request):
    """
    Vista para consultar stock disponible.
    Accesible para todos los roles.
    """
    query = request.GET.get('q', '')
    bodega = request.GET.get('bodega', '')
    
    stock_list = Stock.objects.all()
    
    if query:
        stock_list = stock_list.filter(
            Q(codigo__icontains=query) | 
            Q(descripcion__icontains=query)
        )
        
    if bodega:
        stock_list = stock_list.filter(bodega=bodega)
        
    # Paginación
    paginator = Paginator(stock_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener lista de bodegas para el filtro
    bodegas = Stock.objects.values_list('bodega', 'bodega_nombre').distinct().order_by('bodega')
    
    return render(request, 'bodega/consultar_stock.html', {
        'page_obj': page_obj,
        'query': query,
        'bodega_seleccionada': bodega,
        'bodegas': bodegas
    })

@login_required
@role_required(['admin'])
def historial_cargas(request):
    """
    Historial de cargas de archivos de stock.
    """
    cargas = CargaStock.objects.all()
    paginator = Paginator(cargas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'bodega/historial_cargas.html', {
        'page_obj': page_obj
    })


@login_required
@role_required(['admin', 'bodega'])
def gestion_pedidos(request):
    """
    Panel para que el personal de bodega gestione sus solicitudes pendientes.
    """
    user = request.user
    q = request.GET.get('q', '')
    bodega_filtro = request.GET.get('bodega', '')

    detalles_qs = (
        SolicitudDetalle.objects
        .select_related('reserva')
        .filter(estado_bodega__in=['pendiente', 'preparando'])
        .order_by('id')
    )

    bodegas_usuario = user.get_bodegas_codigos() if hasattr(user, 'get_bodegas_codigos') else []
    if user.es_bodega():
        if bodegas_usuario:
            detalles_qs = detalles_qs.filter(bodega__in=bodegas_usuario)
        else:
            detalles_qs = detalles_qs.none()

    if q:
        detalles_qs = detalles_qs.filter(
            Q(solicitud__cliente__icontains=q)
            | Q(solicitud__numero_pedido__icontains=q)
            | Q(codigo__icontains=q)
        )

    if bodega_filtro:
        detalles_qs = detalles_qs.filter(bodega=bodega_filtro)

    solicitudes_qs = (
        Solicitud.objects
        .filter(detalles__in=detalles_qs)
        .select_related('solicitante')
        .distinct()
        .order_by('fecha_solicitud', 'id')
    )

    prefetch = Prefetch('detalles', queryset=detalles_qs, to_attr='detalles_visibles')

    codigos = list(detalles_qs.values_list('codigo', flat=True))
    stock_qs = Stock.objects.filter(codigo__in=codigos)
    if user.es_bodega() and bodegas_usuario:
        stock_qs = stock_qs.filter(bodega__in=bodegas_usuario)
    stock_map = {}
    for stock in stock_qs:
        stock_map.setdefault(stock.codigo, []).append({
            'bodega': stock.bodega,
            'bodega_nombre': stock.bodega_nombre or '',
            'ubicacion': stock.ubicacion or '',
            'ubicacion_2': stock.ubicacion_2 or '',
            'stock': stock.stock_disponible,
            'descripcion': stock.descripcion or '',
        })

    solicitudes = []
    for solicitud in solicitudes_qs.prefetch_related(prefetch):
        detalles_visibles = getattr(solicitud, 'detalles_visibles', [])
        if not detalles_visibles:
            continue

        detalles_payload = []
        total_cantidad = 0
        for detalle in detalles_visibles:
            stock_detalle = stock_map.get(detalle.codigo, [])
            descripcion_resuelta = detalle.descripcion or (stock_detalle[0]['descripcion'] if stock_detalle else '')
            bodega_sugerida = detalle.bodega or (stock_detalle[0]['bodega'] if stock_detalle else '')
            setattr(detalle, 'descripcion_resuelta', descripcion_resuelta)
            setattr(detalle, 'bodega_sugerida', bodega_sugerida or '')
            setattr(detalle, 'stock_info', stock_detalle)
            detalles_payload.append({
                'id': detalle.id,
                'codigo': detalle.codigo,
                'descripcion': descripcion_resuelta,
                'bodega': detalle.bodega or '-',
                'bodega_sugerida': bodega_sugerida,
                'cantidad': detalle.cantidad,
                'estado': detalle.estado_bodega,
                'estado_label': detalle.get_estado_bodega_display(),
                'url': reverse('bodega:registrar_transferencia', args=[detalle.id]),
                'stock': stock_detalle,
            })
            total_cantidad += detalle.cantidad

        solicitud.modal_detalles = detalles_payload
        solicitud.total_lineas = len(detalles_payload)
        solicitud.total_cantidad = total_cantidad
        solicitud.bodegas_involucradas = sorted({det['bodega'] for det in detalles_payload})
        solicitud.modal_detalles_json = json.dumps(detalles_payload)
        solicitudes.append(solicitud)

    bodegas_disponibles = Bodega.objects.filter(activa=True).order_by('codigo')
    context = {
        'solicitudes': solicitudes,
        'busqueda': q,
        'bodega_filtro': bodega_filtro,
        'bodegas_disponibles': bodegas_disponibles,
        'transferencia_form': TransferenciaForm(),
    }
    return render(request, 'bodega/gestion_pedidos.html', context)


@login_required
@role_required(['admin', 'bodega'])
def registrar_transferencia(request, detalle_id):
    """
    Permite a bodega registrar la transferencia (entrega) de un producto.
    """
    detalle = get_object_or_404(
        SolicitudDetalle.objects.select_related('solicitud', 'reserva'),
        pk=detalle_id
    )

    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    user = request.user
    if user.es_bodega():
        bodegas_usuario = user.get_bodegas_codigos()
        if detalle.bodega and detalle.bodega not in bodegas_usuario:
            mensaje = 'No tienes permiso para gestionar esta bodega.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': mensaje}, status=403)
            messages.error(request, mensaje)
            return redirect('bodega:gestion_pedidos')

    if detalle.estado_bodega == 'preparado':
        mensaje = 'Este producto ya fue entregado a despacho.'
        if is_ajax:
            return JsonResponse({'success': False, 'message': mensaje}, status=400)
        messages.info(request, mensaje)
        return redirect('bodega:gestion_pedidos')

    if request.method == 'POST':
        form = TransferenciaForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            reserva = getattr(detalle, 'reserva', None)

            bodega_origen = resolver_bodega_origen(detalle, request.POST.get('bodega_origen'))

            try:
                transferencia = BodegaTransferencia.objects.create(
                    solicitud=detalle.solicitud,
                    detalle=detalle,
                    reserva=reserva,
                    numero_transferencia=data['numero_transferencia'],
                    fecha_transferencia=data['fecha_transferencia'],
                    hora_transferencia=data['hora_transferencia'],
                    bodega_origen=bodega_origen or 'N/D',
                    bodega_destino=data['bodega_destino'],
                    cantidad=detalle.cantidad,
                    registrado_por=request.user,
                    observaciones=data.get('observaciones', ''),
                )
            except IntegrityError:
                form.add_error('numero_transferencia', 'Este número de transferencia ya existe.')
            else:
                detalle.estado_bodega = 'preparado'
                detalle.preparado_por = request.user
                detalle.fecha_preparacion = timezone.now()
                if bodega_origen:
                    detalle.bodega = bodega_origen
                detalle.save(update_fields=['estado_bodega', 'preparado_por', 'fecha_preparacion', 'bodega'])

                if reserva:
                    reserva.marcar_consumida()

                mover_stock(detalle.codigo, bodega_origen, detalle.cantidad, solicitud=detalle.solicitud)

                # Si todas las líneas están preparadas, mover solicitud a en_despacho
                solicitud = detalle.solicitud
                if not solicitud.detalles.exclude(estado_bodega='preparado').exists():
                    solicitud.estado = 'en_despacho'
                    solicitud.save(update_fields=['estado'])

                mensaje = f'Transferencia {transferencia.numero_transferencia} registrada correctamente.'
                if is_ajax:
                    return JsonResponse({'success': True, 'message': mensaje})
                messages.success(request, mensaje)
                return redirect('bodega:gestion_pedidos')

        if is_ajax:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = TransferenciaForm(initial={
            'fecha_transferencia': timezone.localdate(),
            'hora_transferencia': timezone.localtime().strftime('%H:%M'),
            'bodega_destino': '013',
        })

        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    return render(request, 'bodega/transferencia_form.html', {
        'detalle': detalle,
        'form': form,
    })


@login_required
@role_required(['admin', 'bodega'])
def registrar_transferencia_multiple(request):
    """
    Registra una transferencia para múltiples detalles en un solo paso.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    form = TransferenciaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    detalle_ids = request.POST.getlist('detalle_ids[]') or request.POST.getlist('detalle_ids')
    if not detalle_ids:
        return JsonResponse({'success': False, 'message': 'Debes seleccionar al menos un producto.'}, status=400)

    detalles = list(
        SolicitudDetalle.objects
        .select_related('solicitud', 'reserva')
        .filter(pk__in=detalle_ids, estado_bodega__in=['pendiente', 'preparando'])
    )

    if len(detalles) != len(set(detalle_ids)):
        return JsonResponse({'success': False, 'message': 'Algunos productos no existen o ya fueron entregados.'}, status=400)

    user = request.user
    bodegas_usuario = user.get_bodegas_codigos() if hasattr(user, 'get_bodegas_codigos') else []
    if user.es_bodega():
        for detalle in detalles:
            if detalle.bodega and detalle.bodega not in bodegas_usuario:
                return JsonResponse({
                    'success': False,
                    'message': f'No tienes permiso para gestionar la bodega {detalle.bodega}.'
                }, status=403)

    data = form.cleaned_data
    solicitudes_afectadas = set()

    try:
        with transaction.atomic():
            for detalle in detalles:
                reserva = getattr(detalle, 'reserva', None)
                bodega_origen = resolver_bodega_origen(
                    detalle,
                    request.POST.get(f"bodegas_origen[{detalle.id}]")
                )

                BodegaTransferencia.objects.create(
                    solicitud=detalle.solicitud,
                    detalle=detalle,
                    reserva=reserva,
                    numero_transferencia=data['numero_transferencia'],
                    fecha_transferencia=data['fecha_transferencia'],
                    hora_transferencia=data['hora_transferencia'],
                    bodega_origen=bodega_origen or 'N/D',
                    bodega_destino=data['bodega_destino'],
                    cantidad=detalle.cantidad,
                    registrado_por=request.user,
                    observaciones=data.get('observaciones', ''),
                )

                detalle.estado_bodega = 'preparado'
                detalle.preparado_por = request.user
                detalle.fecha_preparacion = timezone.now()
                if bodega_origen:
                    detalle.bodega = bodega_origen
                detalle.save(update_fields=['estado_bodega', 'preparado_por', 'fecha_preparacion', 'bodega'])

                if reserva:
                    reserva.marcar_consumida()

                mover_stock(detalle.codigo, bodega_origen, detalle.cantidad, solicitud=detalle.solicitud)
                solicitudes_afectadas.add(detalle.solicitud_id)

            for solicitud_id in solicitudes_afectadas:
                solicitud = Solicitud.objects.get(pk=solicitud_id)
                if not solicitud.detalles.exclude(estado_bodega='preparado').exists():
                    solicitud.estado = 'en_despacho'
                    solicitud.save(update_fields=['estado'])

    except IntegrityError as exc:
        return JsonResponse({'success': False, 'message': f'Error al registrar transferencias: {exc}'}, status=400)

    return JsonResponse({
        'success': True,
        'message': f'Se registraron {len(detalles)} productos con la transferencia {data["numero_transferencia"]}.'
    })
