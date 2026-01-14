import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.decorators import role_required
from configuracion.models import TransporteConfig
from solicitudes.models import Solicitud, SolicitudDetalle
from bodega.models import Stock
from .forms import BultoForm, BultoEstadoForm
from .models import Bulto
# BultoSolicitud eliminado - ahora se usa ForeignKey directo


@login_required
@role_required(['admin', 'despacho'])
def gestion_despacho(request):
    """
    Vista principal para crear bultos agrupando solicitudes en despacho.
    """
    q = request.GET.get('q', '')
    transporte = request.GET.get('transporte', '')
    estado_filtro = request.GET.get('estado', 'pendientes')

    estados_pendientes = ['en_despacho', 'embalado', 'listo_despacho']
    estados_todos = ['en_despacho', 'embalado', 'listo_despacho', 'en_ruta', 'despachado']

    estados_consulta = estados_todos if estado_filtro == 'todas' else estados_pendientes

    # Optimización: Prefetch con select_related para evitar queries N+1
    from django.db.models import Prefetch
    
    solicitudes = (
        Solicitud.objects
        .filter(estado__in=estados_consulta)
        .select_related('solicitante')
        .prefetch_related(
            Prefetch(
                'detalles',
                queryset=SolicitudDetalle.objects.select_related('bulto')
            )
        )
        .order_by('fecha_solicitud', 'id')
    )

    if q:
        solicitudes = solicitudes.filter(
            Q(cliente__icontains=q)
            | Q(numero_pedido__icontains=q)
            | Q(numero_st__icontains=q)
            | Q(numero_ot__icontains=q)
            | Q(id__icontains=q)
        )

    if transporte:
        solicitudes = solicitudes.filter(transporte=transporte)

    form = BultoForm()

    # Optimización: Evaluar queryset una sola vez para evitar múltiples queries
    solicitudes = list(solicitudes)
    
    codigos = set()
    for solicitud in solicitudes:
        for d in solicitud.detalles.all():
            codigos.add(d.codigo)

    stock_map = {}
    if codigos:
        for stock in Stock.objects.filter(codigo__in=codigos):
            stock_map[stock.codigo] = stock.descripcion or ''

    for solicitud in solicitudes:
        detalles_payload = []
        total_codigos = 0
        codigos_en_bultos = 0
        codigos_pendientes = 0
        
        for d in solicitud.detalles.all():
            descripcion = d.descripcion or stock_map.get(d.codigo, '')
            total_codigos += 1
            
            if d.bulto_id:
                codigos_en_bultos += 1
            else:
                codigos_pendientes += 1
            
            detalles_payload.append({
                'id': d.id,
                'codigo': d.codigo,
                'descripcion': descripcion,
                'bodega': d.bodega or '-',
                'cantidad': d.cantidad,
                'estado_bodega': d.estado_bodega,
                'estado_bodega_display': d.get_estado_bodega_display(),
                'bulto_id': d.bulto_id,
                'bulto_codigo': d.bulto.codigo if d.bulto else '',
                'preparado': d.estado_bodega == 'preparado',
                'en_bulto': bool(d.bulto_id),
            })
        
        solicitud.detalles_json = json.dumps(detalles_payload)
        solicitud.total_codigos = total_codigos
        solicitud.codigos_en_bultos = codigos_en_bultos
        solicitud.codigos_pendientes = codigos_pendientes

    bultos = (
        Bulto.objects
        .select_related('creado_por', 'solicitud')
        .order_by('-fecha_creacion')[:50]
    )

    transportes = TransporteConfig.activos()

    context = {
        'solicitudes': solicitudes,
        'estado_filtro': estado_filtro,
        'transporte': transporte,
        'busqueda': q,
        'form': form,
        'transportes': transportes,
        'bultos': bultos,
    }
    return render(request, 'despacho/gestion.html', context)


@login_required
@role_required(['admin', 'despacho'])
def crear_bulto(request):
    if request.method != 'POST':
        messages.error(request, 'Método no permitido.')
        return redirect('despacho:gestion')

    form = BultoForm(request.POST)
    raw_ids = request.POST.get('detalle_ids', '')
    detalle_ids = [pk for pk in raw_ids.split(',') if pk]

    if not detalle_ids:
        messages.error(request, 'Debes seleccionar al menos un código.')
        return redirect('despacho:gestion')

    detalles = list(
        SolicitudDetalle.objects
        .select_related('solicitud')
        .filter(id__in=detalle_ids, solicitud__estado__in=['en_despacho', 'embalado'])
    )

    if len(detalles) != len(set(detalle_ids)):
        messages.error(request, 'Algunos productos no existen o ya fueron asignados a otro bulto.')
        return redirect('despacho:gestion')

    detalles_invalidos = [d for d in detalles if d.bulto_id]

    if detalles_invalidos:
        mensajes = ', '.join(f'{d.codigo} (Solicitud #{d.solicitud_id})' for d in detalles_invalidos[:5])
        messages.error(request, f'Estos productos ya están en un bulto: {mensajes}')
        return redirect('despacho:gestion')

    # Verificar que todos los detalles estén preparados (con stock transferido)
    # EXCEPCIÓN: Si la solicitud no afecta stock (despacho directo), permitir crear bulto sin preparación
    detalles_no_preparados = [d for d in detalles if d.estado_bodega != 'preparado']
    if detalles_no_preparados:
        # Verificar si todas las solicitudes no afectan stock
        # Si todas las solicitudes no afectan stock, permitir continuar
        todas_no_afectan_stock = all(not d.solicitud.afecta_stock for d in detalles_no_preparados)
        if not todas_no_afectan_stock:
            mensajes = ', '.join(f'{d.codigo} (Solicitud #{d.solicitud_id})' for d in detalles_no_preparados[:5])
            messages.error(request, f'Estos productos no han sido preparados por bodega: {mensajes}')
            return redirect('despacho:gestion')

    # Validar que todos los detalles pertenezcan a la misma solicitud
    # Un bulto solo puede estar asociado a una solicitud
    solicitudes_detalles = {detalle.solicitud_id for detalle in detalles}
    if len(solicitudes_detalles) > 1:
        solicitudes_ids = ', '.join(f'#{sid}' for sid in sorted(list(solicitudes_detalles))[:3])
        messages.error(
            request,
            f'Un bulto solo puede contener productos de una sola solicitud. '
            f'Solicitudes detectadas: {solicitudes_ids}'
        )
        return redirect('despacho:gestion')

    # Obtener la única solicitud
    solicitud_unica = detalles[0].solicitud

    if form.is_valid():
        with transaction.atomic():
            bulto = form.save(commit=False)
            bulto.creado_por = request.user
            bulto.estado = 'embalado'
            # Asignar la solicitud ANTES de guardar (campo obligatorio NOT NULL)
            bulto.solicitud = solicitud_unica
            # Establecer fecha_embalaje automáticamente al crear el bulto
            # fecha_embalaje es la fecha real del proceso (fecha_creacion no afecta el KPI)
            if not bulto.fecha_embalaje:
                bulto.fecha_embalaje = timezone.now()
            bulto.save()

            # Asignar bulto a todos los detalles
            for detalle in detalles:
                detalle.bulto = bulto
                detalle.save(update_fields=['bulto'])
            
            # Si todos los detalles de la solicitud están en bultos, cambiar estado
            if not solicitud_unica.detalles.filter(bulto__isnull=True).exists():
                solicitud_unica.estado = 'listo_despacho'
                solicitud_unica.save(update_fields=['estado'])

            mensaje = f'Bulto {bulto.codigo} creado con {len(detalles)} códigos.'
            messages.success(request, mensaje)
            return redirect('despacho:detalle_bulto', pk=bulto.pk)
    else:
        messages.error(request, 'Debes completar los datos del bulto.')

    return redirect('despacho:gestion')


@login_required
@role_required(['admin', 'despacho'])
def detalle_bulto(request, pk):
    bulto = get_object_or_404(Bulto.objects.select_related('creado_por', 'solicitud'), pk=pk)
    detalles = bulto.detalles.select_related('solicitud')
    form = BultoEstadoForm(instance=bulto)

    # Obtener información de numeración de bultos (ej: 1-1, 1-2, 2-2)
    solicitud = bulto.solicitud
    numero_bulto = None
    total_bultos = None
    
    if solicitud:
        # Obtener todos los bultos de esta solicitud ordenados por fecha de creación
        bultos_solicitud = solicitud.bultos.all().order_by('fecha_creacion')
        total_bultos = bultos_solicitud.count()
        
        # Encontrar el índice de este bulto (1-based)
        for idx, b in enumerate(bultos_solicitud, 1):
            if b.id == bulto.id:
                numero_bulto = idx
                break

    # Asegurar que siempre tengamos valores por defecto
    context = {
        'bulto': bulto,
        'detalles': detalles,
        'estado_form': form,
        'solicitud': solicitud,
        'numero_bulto': numero_bulto or None,
        'total_bultos': total_bultos or None,
    }
    
    return render(request, 'despacho/detalle_bulto.html', context)


@login_required
@role_required(['admin', 'despacho'])
def actualizar_estado_bulto(request, pk):
    bulto = get_object_or_404(Bulto, pk=pk)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    # Validar que solo admin puede marcar bultos como 'finalizado' manualmente
    nuevo_estado = request.POST.get('estado')
    if nuevo_estado == 'finalizado' and not request.user.es_admin():
        return JsonResponse({
            'success': False,
            'message': 'Solo el administrador puede finalizar bultos manualmente.'
        }, status=403)

    form = BultoEstadoForm(request.POST, instance=bulto)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    bulto = form.save()

    # Establecer fecha_embalaje automáticamente si el bulto se marca como embalado o listo para despacho
    if bulto.estado in ['embalado', 'listo_despacho'] and not bulto.fecha_embalaje:
        bulto.fecha_embalaje = timezone.now()
        bulto.save(update_fields=['fecha_embalaje'])

    # Un bulto solo puede tener una solicitud (ahora es ForeignKey directo)
    solicitud = bulto.solicitud
    
    if solicitud:
        if bulto.estado == 'finalizado':
            # Estado terminal: cuando un bulto se marca como finalizado,
            # la solicitud debe estar en 'despachado' (estado final del ciclo)
            if not bulto.fecha_entrega:
                bulto.fecha_entrega = timezone.now()
                bulto.save(update_fields=['fecha_entrega'])
            
            # Si la solicitud no está despachada, actualizarla (sincronización)
            if solicitud.estado != 'despachado':
                solicitud.estado = 'despachado'
                solicitud.save(update_fields=['estado'])
        elif bulto.estado == 'entregado':
            # Mantener lógica existente para 'entregado' (estado intermedio)
            bulto.fecha_entrega = bulto.fecha_entrega or timezone.now()
            bulto.save(update_fields=['fecha_entrega'])
            if solicitud.estado != 'despachado':
                solicitud.estado = 'despachado'
                solicitud.save(update_fields=['estado'])
        elif bulto.estado == 'en_ruta':
            if not bulto.fecha_envio:
                bulto.fecha_envio = timezone.now()
                bulto.save(update_fields=['fecha_envio'])
            if solicitud.estado != 'en_ruta':
                solicitud.estado = 'en_ruta'
                solicitud.save(update_fields=['estado'])
        elif bulto.estado == 'listo_despacho':
            if solicitud.estado not in ['listo_despacho', 'en_ruta', 'despachado']:
                solicitud.estado = 'listo_despacho'
                solicitud.save(update_fields=['estado'])

    return JsonResponse({'success': True})
