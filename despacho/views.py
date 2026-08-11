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
    solicitud_filtro = request.GET.get('solicitud', '')

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

    if solicitud_filtro:
        try:
            sid = int(solicitud_filtro)
            solicitudes = solicitudes.filter(pk=sid)
        except (ValueError, TypeError):
            pass

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
        'solicitud_filtro': solicitud_filtro,
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
    raw_paquete = request.POST.get('paquete_datos', '')
    
    try:
        paquete_items = json.loads(raw_paquete)
        detalle_ids = [int(item['id']) for item in paquete_items]
        cantidades_map = {int(item['id']): int(item['cantidad']) for item in paquete_items}
    except (json.JSONDecodeError, ValueError, KeyError, TypeError):
        # Fallback a formato antiguo por si acaso
        raw_ids = request.POST.get('detalle_ids', '')
        detalle_ids = [int(pk) for pk in raw_ids.split(',') if pk]
        cantidades_map = {}

    if not detalle_ids:
        messages.error(request, 'Debes seleccionar al menos un código con cantidad válida.')
        return redirect('despacho:gestion')

    unidades_por_bulto_str = request.POST.get('unidades_por_bulto')
    unidades_por_bulto = None
    if unidades_por_bulto_str and unidades_por_bulto_str.isdigit() and int(unidades_por_bulto_str) > 0:
        unidades_por_bulto = int(unidades_por_bulto_str)

    if unidades_por_bulto and len(detalle_ids) > 1:
        messages.error(request, 'La creación múltiple solo es válida cuando seleccionas exactamente 1 código.')
        return redirect('despacho:gestion')

    detalles = list(
        SolicitudDetalle.objects
        .select_related('solicitud')
        .filter(id__in=detalle_ids, solicitud__estado__in=['en_despacho', 'embalado', 'listo_despacho'])
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

    # Identificar todas las solicitudes involucradas
    solicitudes_ids = {detalle.solicitud_id for detalle in detalles}
    solicitudes_afectadas = Solicitud.objects.filter(id__in=solicitudes_ids)

    if form.is_valid():
        es_despachador = request.user.es_despacho()
        bultos_creados = []
        
        with transaction.atomic():
            if unidades_por_bulto and len(detalles) == 1:
                # MODO MULTIPLE (LOTE)
                detalle_original = detalles[0]
                cantidad_total = cantidades_map.get(detalle_original.id, detalle_original.cantidad)
                
                if unidades_por_bulto >= cantidad_total:
                    bultos_a_crear = [(cantidad_total, False)]
                else:
                    bultos_completos = cantidad_total // unidades_por_bulto
                    resto = cantidad_total % unidades_por_bulto
                    bultos_a_crear = [(unidades_por_bulto, False)] * bultos_completos
                    if resto > 0:
                        bultos_a_crear.append((resto, True))
                
                for idx, (cant_asignar, es_resto) in enumerate(bultos_a_crear):
                    bulto = form.save(commit=False)
                    bulto.pk = None # Instancia nueva
                    bulto.codigo = ''
                    bulto.creado_por = request.user
                    bulto.estado = 'listo_despacho' if es_despachador else 'embalado'
                    bulto.solicitud = solicitudes_afectadas.first()
                    bulto.fecha_embalaje = timezone.now()
                    bulto.save()
                    bultos_creados.append(bulto.pk)
                    
                    if cant_asignar < detalle_original.cantidad:
                        clon = SolicitudDetalle.objects.get(pk=detalle_original.pk)
                        clon.pk = None
                        clon.cantidad = cant_asignar
                        clon.bulto = bulto
                        clon.save()
                        
                        detalle_original.cantidad -= cant_asignar
                        detalle_original.save(update_fields=['cantidad'])
                    else:
                        detalle_original.bulto = bulto
                        detalle_original.save(update_fields=['bulto'])
                        
            else:
                # MODO NORMAL (1 solo bulto consolidado)
                bulto = form.save(commit=False)
                bulto.creado_por = request.user
                
                if es_despachador:
                    bulto.estado = 'listo_despacho'
                else:
                    bulto.estado = 'embalado'
                
                if len(solicitudes_ids) == 1:
                    bulto.solicitud = solicitudes_afectadas.first()
                else:
                    bulto.solicitud = None
                    
                bulto.fecha_embalaje = timezone.now()
                bulto.save()
                bultos_creados.append(bulto.pk)
    
                for detalle in detalles:
                    cantidad_a_embalar = cantidades_map.get(detalle.id, detalle.cantidad)
                    if cantidad_a_embalar <= 0: continue
                        
                    if cantidad_a_embalar < detalle.cantidad:
                        cantidad_restante = detalle.cantidad - cantidad_a_embalar
                        detalle.cantidad = cantidad_restante
                        detalle.save(update_fields=['cantidad'])
                        
                        clon = SolicitudDetalle.objects.get(pk=detalle.pk)
                        clon.pk = None
                        clon.cantidad = cantidad_a_embalar
                        clon.bulto = bulto
                        clon.save()
                    else:
                        detalle.bulto = bulto
                        detalle.save(update_fields=['bulto'])
            
            # Actualizar estado de TODAS las solicitudes involucradas
            for sol in solicitudes_afectadas:
                if not sol.detalles.filter(bulto__isnull=True).exists():
                    sol.estado = 'listo_despacho'
                    sol.save(update_fields=['estado'])

            if len(bultos_creados) > 1:
                messages.success(request, f'Se crearon {len(bultos_creados)} bultos automáticamente.')
                # Redirigir a vista de lote (por hacer)
                return redirect('despacho:lote_bultos', ids=','.join(map(str, bultos_creados)))
            else:
                mensaje = f'Bulto {Bulto.objects.get(pk=bultos_creados[0]).codigo} creado exitosamente.'
                messages.success(request, mensaje)
                return redirect('despacho:detalle_bulto', pk=bultos_creados[0])
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
    
    # Si es multi-solicitud, intentar tomar la primera como referencia para la UI
    if not solicitud:
        primer_detalle = detalles.first()
        if primer_detalle:
            solicitud = primer_detalle.solicitud

    numero_bulto = None
    total_bultos = None
    
    # La numeración solo tiene sentido si el bulto está vinculado formalmente a una sola solicitud
    if bulto.solicitud:
        # Obtener todos los bultos de esta solicitud ordenados por fecha de creación
        bultos_solicitud = bulto.solicitud.bultos.all().order_by('fecha_creacion')
        total_bultos = bultos_solicitud.count()
        
        # Encontrar el índice de este bulto (1-based)
        for idx, b in enumerate(bultos_solicitud, 1):
            if b.id == bulto.id:
                numero_bulto = idx
                break

    # Asegurar que siempre tengamos valores por defecto
    
    import json
    
    # Recopilar todas las solicitudes vinculadas al bulto para la etiqueta
    solicitudes_unicas = set()
    for d in detalles:
        solicitudes_unicas.add(d.solicitud)
        
    solicitudes_etiqueta = []
    for s in solicitudes_unicas:
        numero = s.numero_st if s.tipo == 'ST' else s.numero_pedido
        solicitudes_etiqueta.append({
            'id': s.id,
            'numero': numero or '-',
            'tipo': s.get_tipo_display() or s.tipo,
            'cliente': s.cliente or '-'
        })

    context = {
        'bulto': bulto,
        'detalles': detalles,
        'estado_form': form,
        'solicitud': solicitud,
        'numero_bulto': numero_bulto or None,
        'total_bultos': total_bultos or None,
        'solicitudes_etiqueta_json': json.dumps(solicitudes_etiqueta),
    }
    
    return render(request, 'despacho/detalle_bulto.html', context)


@login_required
@role_required(['admin', 'despacho'])
def actualizar_estado_bulto(request, pk):
    bulto = get_object_or_404(Bulto, pk=pk)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

    # Solo el admin puede actualizar el estado del bulto (el despachador no ve esta opción)
    if not request.user.es_admin():
        return JsonResponse({
            'success': False,
            'message': 'Solo el administrador puede actualizar el estado de los bultos.'
        }, status=403)

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
    
    # Obtener todas las solicitudes que tienen ítems en este bulto
    solicitudes_ids = bulto.detalles.values_list('solicitud_id', flat=True).distinct()
    solicitudes_afectadas = Solicitud.objects.filter(id__in=solicitudes_ids)
    
    for sol in solicitudes_afectadas:
        if bulto.estado == 'finalizado':
            if not bulto.fecha_entrega:
                bulto.fecha_entrega = timezone.now()
                bulto.save(update_fields=['fecha_entrega'])
            
            if sol.estado != 'despachado':
                sol.estado = 'despachado'
                sol.save(update_fields=['estado'])
        elif bulto.estado == 'entregado':
            bulto.fecha_entrega = bulto.fecha_entrega or timezone.now()
            bulto.save(update_fields=['fecha_entrega'])
            if sol.estado != 'despachado':
                sol.estado = 'despachado'
                sol.save(update_fields=['estado'])
        elif bulto.estado == 'en_ruta':
            if not bulto.fecha_envio:
                bulto.fecha_envio = timezone.now()
                bulto.save(update_fields=['fecha_envio'])
            if sol.estado != 'en_ruta':
                sol.estado = 'en_ruta'
                sol.save(update_fields=['estado'])
        elif bulto.estado == 'listo_despacho':
            if sol.estado not in ['listo_despacho', 'en_ruta', 'despachado']:
                sol.estado = 'listo_despacho'
                sol.save(update_fields=['estado'])

    return JsonResponse({'success': True})

@login_required
@role_required(['admin', 'despacho'])
def lote_bultos(request, ids):
    bulto_ids = [int(pk) for pk in ids.split(',') if pk.isdigit()]
    bultos = Bulto.objects.filter(id__in=bulto_ids).select_related('solicitud')
    
    if not bultos.exists():
        messages.error(request, 'No se encontraron bultos en este lote.')
        return redirect('despacho:gestion')
        
    context = {
        'bultos': bultos,
        'ids_str': ids
    }
    return render(request, 'despacho/lote_bultos.html', context)


@login_required
@role_required(['admin', 'despacho'])
def imprimir_lote(request, ids):
    bulto_ids = [int(pk) for pk in ids.split(',') if pk.isdigit()]
    bultos = Bulto.objects.filter(id__in=bulto_ids).prefetch_related('detalles__solicitud').select_related('solicitud')
    
    import json
    
    bultos_data = []
    
    # Simular la lógica de detalle_bulto para cada uno
    for idx, bulto in enumerate(bultos):
        solicitudes_unicas = set()
        for d in bulto.detalles.all():
            solicitudes_unicas.add(d.solicitud)
            
        solicitudes_etiqueta = []
        for s in solicitudes_unicas:
            numero = s.numero_st if s.tipo == 'ST' else s.numero_pedido
            solicitudes_etiqueta.append({
                'id': s.id,
                'numero': numero or '-',
                'tipo': s.get_tipo_display() or s.tipo,
                'cliente': s.cliente or '-'
            })
            
        bultos_data.append({
            'codigo': bulto.codigo,
            'peso': float(bulto.peso_total or 0),
            'largo': float(bulto.largo_cm or 0),
            'ancho': float(bulto.ancho_cm or 0),
            'alto': float(bulto.alto_cm or 0),
            'tipo': bulto.get_tipo_display(),
            'transportista': bulto.get_transportista_display(),
            'numero_bulto': idx + 1,
            'total_bultos': len(bultos),
            'solicitudes_json': json.dumps(solicitudes_etiqueta),
        })

    context = {
        'bultos_json': json.dumps(bultos_data),
        'bultos_count': len(bultos_data),
    }
    return render(request, 'despacho/imprimir_lote.html', context)

@login_required
@role_required(['admin', 'despacho', 'bodega'])
def imprimir_bultos_solicitud(request, pk):
    solicitud = get_object_or_404(Solicitud, pk=pk)
    
    # Obtener todos los bultos que tengan detalles de esta solicitud
    bultos_ids = solicitud.detalles.filter(bulto__isnull=False).values_list('bulto_id', flat=True).distinct()
    
    if not bultos_ids:
        messages.error(request, 'No hay bultos generados para esta solicitud.')
        return redirect('despacho:gestion')
        
    ids_str = ','.join(map(str, bultos_ids))
    return imprimir_lote(request, ids_str)
