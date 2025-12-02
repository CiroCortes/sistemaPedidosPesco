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
from .models import Bulto, BultoSolicitud


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

    solicitudes = (
        Solicitud.objects
        .filter(estado__in=estados_consulta)
        .select_related('solicitante')
        .prefetch_related('detalles')
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
        .select_related('creado_por')
        .prefetch_related('solicitudes')
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
    detalles_no_preparados = [d for d in detalles if d.estado_bodega != 'preparado']
    if detalles_no_preparados:
        mensajes = ', '.join(f'{d.codigo} (Solicitud #{d.solicitud_id})' for d in detalles_no_preparados[:5])
        messages.error(request, f'Estos productos no han sido preparados por bodega: {mensajes}')
        return redirect('despacho:gestion')

    if form.is_valid():
        with transaction.atomic():
            bulto = form.save(commit=False)
            bulto.creado_por = request.user
            bulto.estado = 'embalado'
            bulto.save()

            solicitudes_afectadas = set()

            for detalle in detalles:
                detalle.bulto = bulto
                detalle.save(update_fields=['bulto'])
                solicitudes_afectadas.add(detalle.solicitud)

            for solicitud in solicitudes_afectadas:
                BultoSolicitud.objects.get_or_create(bulto=bulto, solicitud=solicitud)
                if not solicitud.detalles.filter(bulto__isnull=True).exists():
                    solicitud.estado = 'listo_despacho'
                    solicitud.save(update_fields=['estado'])

            mensaje = f'Bulto {bulto.codigo} creado con {len(detalles)} códigos.'
            messages.success(request, mensaje)
            return redirect('despacho:detalle_bulto', pk=bulto.pk)
    else:
        messages.error(request, 'Debes completar los datos del bulto.')

    return redirect('despacho:gestion')


@login_required
@role_required(['admin', 'despacho'])
def detalle_bulto(request, pk):
    bulto = get_object_or_404(Bulto.objects.select_related('creado_por'), pk=pk)
    detalles = bulto.detalles.select_related('solicitud')
    form = BultoEstadoForm(instance=bulto)

    return render(request, 'despacho/detalle_bulto.html', {
        'bulto': bulto,
        'detalles': detalles,
        'estado_form': form,
    })


@login_required
@role_required(['admin', 'despacho'])
def actualizar_estado_bulto(request, pk):
    bulto = get_object_or_404(Bulto, pk=pk)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    form = BultoEstadoForm(request.POST, instance=bulto)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    bulto = form.save()

    # Establecer fecha_embalaje automáticamente si el bulto se marca como embalado o listo para despacho
    if bulto.estado in ['embalado', 'listo_despacho'] and not bulto.fecha_embalaje:
        bulto.fecha_embalaje = timezone.now()
        bulto.save(update_fields=['fecha_embalaje'])

    if bulto.estado == 'entregado':
        bulto.fecha_entrega = bulto.fecha_entrega or timezone.now()
        bulto.save(update_fields=['fecha_entrega'])
        for solicitud in bulto.solicitudes.all():
            if solicitud.estado != 'despachado':
                solicitud.estado = 'despachado'
                solicitud.save(update_fields=['estado'])
    elif bulto.estado == 'en_ruta':
        if not bulto.fecha_envio:
            bulto.fecha_envio = timezone.now()
            bulto.save(update_fields=['fecha_envio'])
        for solicitud in bulto.solicitudes.all():
            if solicitud.estado != 'en_ruta':
                solicitud.estado = 'en_ruta'
                solicitud.save(update_fields=['estado'])
    elif bulto.estado == 'listo_despacho':
        for solicitud in bulto.solicitudes.all():
            if solicitud.estado not in ['listo_despacho', 'en_ruta', 'despachado']:
                solicitud.estado = 'listo_despacho'
                solicitud.save(update_fields=['estado'])

    return JsonResponse({'success': True})
