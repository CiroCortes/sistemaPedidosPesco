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
from configuracion.models import EstadoWorkflow, TipoSolicitud
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
        # Excluir bodega='013' que es solo despacho y no requiere preparación
        detalles_pendientes = SolicitudDetalle.objects.filter(
            solicitud=OuterRef('pk'),
            bodega__in=bodegas_usuario,
            estado_bodega='pendiente'
        ).exclude(bodega='013')  # Bodega 013 es solo despacho
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
        'tipos': [(t.codigo, t.nombre) for t in TipoSolicitud.activos()] if TipoSolicitud.activos().exists() else Solicitud.TIPOS,
        'estados_config': estados_opciones,
    }
    return render(request, 'solicitudes/lista.html', context)


@login_required
@role_required(['admin'])
def crear_solicitud(request):
    """
    Permite al admin registrar nuevas solicitudes.
    VALIDA STOCK: Crea solicitud solo con códigos que tienen stock.
    Si hay un solo código y no tiene stock, rechaza la solicitud.
    """
    from bodega.models import Stock
    
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
                # ⚠️ VALIDACIÓN DE STOCK: Separar códigos con stock de los que no tienen
                detalles_con_stock = []
                detalles_sin_stock = []
                
                for cd in detalles_validos:
                    codigo = cd.get('codigo') or 'SC'
                    cantidad = cd.get('cantidad')
                    bodega_asignada = (cd.get('bodega') or '').strip()
                    
                    # Bodega 013 no requiere validación de stock - siempre permitir
                    if bodega_asignada == '013':
                        detalles_con_stock.append(cd)
                        continue
                    
                    # Si no hay bodega asignada, no tiene stock
                    if not bodega_asignada:
                        detalles_sin_stock.append({
                            'codigo': codigo,
                            'descripcion': cd.get('descripcion', ''),
                            'cantidad': cantidad,
                            'bodega': 'Sin asignar',
                            'problema': 'No tiene bodega asignada',
                            'stock_disponible': None
                        })
                        continue
                    
                    # Validar stock en la bodega asignada
                    stock_bodega = Stock.objects.filter(
                        codigo=codigo,
                        bodega=bodega_asignada
                    ).first()
                    
                    if not stock_bodega:
                        detalles_sin_stock.append({
                            'codigo': codigo,
                            'descripcion': cd.get('descripcion', ''),
                            'cantidad': cantidad,
                            'bodega': bodega_asignada,
                            'problema': f'El código no existe en bodega {bodega_asignada}',
                            'stock_disponible': 0
                        })
                    elif stock_bodega.stock_disponible < cantidad:
                        faltante = cantidad - stock_bodega.stock_disponible
                        detalles_sin_stock.append({
                            'codigo': codigo,
                            'descripcion': cd.get('descripcion', ''),
                            'cantidad': cantidad,
                            'bodega': bodega_asignada,
                            'problema': f'Stock insuficiente: tiene {stock_bodega.stock_disponible}, se solicitan {cantidad}',
                            'stock_disponible': stock_bodega.stock_disponible,
                            'faltante': faltante
                        })
                    else:
                        # Stock suficiente, agregar a los que tienen stock
                        detalles_con_stock.append(cd)
                
                # ⚠️ REGLA CRÍTICA: Si hay un solo código y no tiene stock, NO crear la solicitud
                if len(detalles_validos) == 1 and len(detalles_sin_stock) == 1:
                    error = detalles_sin_stock[0]
                    if error['stock_disponible'] is None:
                        mensaje = (
                            f'❌ NO SE PUEDE CREAR LA SOLICITUD: El código {error["codigo"]} '
                            f'({error["descripcion"][:30]}...) no tiene bodega asignada. '
                            f'Cantidad solicitada: {error["cantidad"]}'
                        )
                    else:
                        mensaje = (
                            f'❌ NO SE PUEDE CREAR LA SOLICITUD: El código {error["codigo"]} '
                            f'({error["descripcion"][:30]}...) no tiene stock disponible. '
                            f'Bodega {error["bodega"]} - {error["problema"]}'
                        )
                        if error.get('faltante'):
                            mensaje += f' (faltan {error["faltante"]} unidades)'
                    messages.error(request, mensaje)
                    return render(request, 'solicitudes/formulario.html', {
                        'form': form, 
                        'formset': formset
                    })
                
                # Si hay múltiples códigos y algunos no tienen stock, crear solo con los que tienen stock
                if detalles_sin_stock:
                    mensaje_principal = (
                        f'⚠️ ATENCIÓN: {len(detalles_sin_stock)} producto(s) no tienen stock disponible '
                        f'y NO se incluirán en la solicitud. Se crearán {len(detalles_con_stock)} producto(s) con stock.'
                    )
                    messages.warning(request, mensaje_principal)
                    
                    # Mostrar detalles de productos sin stock
                    for error in detalles_sin_stock:
                        if error['stock_disponible'] is None:
                            mensaje_detalle = (
                                f"  ❌ {error['codigo']} ({error['descripcion'][:30]}...): "
                                f"{error['problema']} - Cantidad: {error['cantidad']}"
                            )
                        else:
                            mensaje_detalle = (
                                f"  ❌ {error['codigo']} ({error['descripcion'][:30]}...): "
                                f"Bodega {error['bodega']} - {error['problema']}"
                            )
                            if error.get('faltante'):
                                mensaje_detalle += f" (faltan {error['faltante']} unidades)"
                        messages.warning(request, mensaje_detalle)
                    
                    # Informar que estos productos se pueden agregar después cuando haya stock
                    messages.info(
                        request, 
                        f'💡 Estos productos se pueden agregar a la solicitud después cuando haya stock disponible.'
                    )
                
                # Si no hay códigos con stock, no crear la solicitud
                if not detalles_con_stock:
                    messages.error(
                        request, 
                        '❌ NO SE PUEDE CREAR LA SOLICITUD: Ningún producto tiene stock disponible.'
                    )
                    return render(request, 'solicitudes/formulario.html', {
                        'form': form, 
                        'formset': formset
                    })
                
                # Crear la solicitud SOLO con los códigos que tienen stock
                solicitud = form.save(commit=False)
                solicitud.solicitante = request.user

                # Tomar la primera línea de los que tienen stock como resumen para cabecera
                primera = detalles_con_stock[0]
                solicitud.codigo = primera.get('codigo') or 'SC'
                solicitud.descripcion = primera.get('descripcion') or ''
                solicitud.cantidad_solicitada = primera.get('cantidad')
                
                # LÓGICA: Si todos los detalles tienen bodega='013', la solicitud va directo a despacho
                todas_bodega_013 = all(
                    (cd.get('bodega') or '').strip() == '013' 
                    for cd in detalles_con_stock
                )
                if todas_bodega_013:
                    solicitud.estado = 'en_despacho'

                solicitud.save()

                # Guardar SOLO las líneas que tienen stock
                for cd in detalles_con_stock:
                    bodega_detalle = (cd.get('bodega') or '').strip()
                    estado_bodega_inicial = 'preparado' if todas_bodega_013 else 'pendiente'
                    
                    solicitud.detalles.create(
                        codigo=cd.get('codigo') or 'SC',
                        descripcion=cd.get('descripcion') or '',
                        cantidad=cd.get('cantidad'),
                        bodega=bodega_detalle,
                        estado_bodega=estado_bodega_inicial,
                    )

                messages.success(
                    request, 
                    f'✅ Solicitud #{solicitud.id} creada correctamente con {len(detalles_con_stock)} producto(s).'
                )
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

    # Validación de acceso mejorada
    if request.user.es_bodega():
        # Verificar que la solicitud tenga detalles de las bodegas del usuario
        bodegas_usuario = request.user.get_bodegas_codigos()
        if not bodegas_usuario:
            messages.warning(request, 'No tienes bodegas asignadas.')
            return redirect('solicitudes:lista')
        
        # Verificar que la solicitud tenga detalles pendientes de sus bodegas
        tiene_detalles_bodega = solicitud.detalles.filter(
            bodega__in=bodegas_usuario,
            estado_bodega='pendiente'
        ).exclude(bodega='013').exists()
        
        if not tiene_detalles_bodega or solicitud.estado != 'pendiente':
            messages.warning(request, 'No puedes acceder a solicitudes fuera de tu módulo.')
            return redirect('solicitudes:lista')
            
    if request.user.es_despacho() and solicitud.estado not in ['en_despacho', 'embalado', 'listo_despacho', 'en_ruta']:
        messages.warning(request, 'No puedes acceder a solicitudes fuera de tu módulo.')
        return redirect('solicitudes:lista')

    detalles = solicitud.detalles.all()
    
    # Filtrar detalles si es usuario de bodega
    # Excluir bodega='013' que es solo despacho y no requiere preparación
    if request.user.es_bodega():
        bodegas_usuario = request.user.get_bodegas_codigos()
        detalles = detalles.filter(bodega__in=bodegas_usuario).exclude(bodega='013')
        
    return render(request, 'solicitudes/detalle.html', {'solicitud': solicitud, 'detalles': detalles})


@login_required
def preparar_producto(request, detalle_id):
    """
    Marca un producto específico como preparado por el usuario de bodega.
    """
    from django.utils import timezone
    from .models import SolicitudDetalle
    
    detalle = get_object_or_404(SolicitudDetalle, pk=detalle_id)
    
    # Bodega '013' no requiere preparación - es solo despacho
    if detalle.bodega == '013':
        messages.error(request, 'Los productos con bodega 013 no requieren preparación. Van directo a despacho.')
        return redirect('solicitudes:detalle', pk=detalle.solicitud.id)
    
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
    Si el estado cambia a 'despachado', finaliza automáticamente los bultos asociados.
    """
    solicitud = get_object_or_404(Solicitud, pk=pk)
    estado_anterior = solicitud.estado  # Guardar estado antes de editar
    
    if request.method == 'POST':
        form = SolicitudEdicionAdminForm(request.POST, instance=solicitud)
        formset = SolicitudDetalleFormSet(request.POST, instance=solicitud)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Recargar la solicitud para obtener el estado actualizado del formulario
            solicitud.refresh_from_db()
            nuevo_estado = solicitud.estado
            
            # Si el estado cambió a 'despachado', finalizar bultos automáticamente (si los tiene)
            if nuevo_estado == 'despachado' and estado_anterior != 'despachado':
                from despacho.models import Bulto
                from django.utils import timezone
                from .services import descontar_stock_despachado
                import logging
                
                logger = logging.getLogger(__name__)
                
                print(f"\n{'='*60}")
                print(f"🚚 PROCESANDO DESPACHO DESDE EDICIÓN - Solicitud #{solicitud.id}")
                print(f"{'='*60}")
                print(f"   Estado anterior: {estado_anterior}")
                print(f"   Nuevo estado: {nuevo_estado}")
                print(f"   Afecta stock: {solicitud.afecta_stock}")
                
                # BUSCAR TODOS los bultos asociados a esta solicitud (si los tiene)
                bultos_asociados = Bulto.objects.filter(solicitud=solicitud)
                total_bultos = bultos_asociados.count()
                
                print(f"\n📦 ACTUALIZACIÓN DE BULTOS:")
                print(f"   Bultos encontrados: {total_bultos}")
                logger.info(f"Finalizando bultos desde edición para solicitud #{solicitud.id}. Total: {total_bultos}")
                
                bultos_actualizados = 0
                if total_bultos > 0:
                    # Si tiene bultos, finalizarlos
                    ahora = timezone.now()
                    
                    for bulto in bultos_asociados:
                        estado_anterior_bulto = bulto.estado
                        print(f"\n   📦 Bulto {bulto.codigo}:")
                        print(f"      Estado anterior: '{estado_anterior_bulto}'")
                        
                        # SIEMPRE actualizar a 'finalizado' cuando la solicitud está despachada
                        bulto.estado = 'finalizado'
                        campos_actualizar = ['estado']
                        
                        # Establecer fechas si no existen
                        if not bulto.fecha_entrega:
                            bulto.fecha_entrega = ahora
                            campos_actualizar.append('fecha_entrega')
                            print(f"      ✅ Fecha entrega establecida: {bulto.fecha_entrega}")
                        
                        if not bulto.fecha_envio:
                            bulto.fecha_envio = ahora
                            campos_actualizar.append('fecha_envio')
                            print(f"      ✅ Fecha envío establecida: {bulto.fecha_envio}")
                        
                        try:
                            bulto.save(update_fields=campos_actualizar)
                            bultos_actualizados += 1
                            print(f"      ✅ Bulto actualizado a 'finalizado'")
                            logger.info(f"Bulto {bulto.codigo} finalizado desde edición para solicitud #{solicitud.id}")
                        except Exception as e:
                            print(f"      ❌ ERROR al guardar bulto: {e}")
                            logger.error(f"Error al finalizar bulto {bulto.codigo}: {e}", exc_info=True)
                else:
                    print(f"   ℹ️  No se encontraron bultos asociados (puede ser Retira Cliente sin bulto)")
                    logger.info(f"Solicitud #{solicitud.id} marcada como despachada sin bultos (Retira Cliente)")
                
                # Actualizar detalles que tienen bulto asignado (si los hay)
                detalles_con_bulto = solicitud.detalles.filter(bulto__isnull=False)
                if detalles_con_bulto.exists():
                    detalles_actualizados = detalles_con_bulto.exclude(estado_bodega='preparado').update(estado_bodega='preparado')
                    if detalles_actualizados > 0:
                        logger.info(f"{detalles_actualizados} detalles actualizados a 'preparado' para solicitud #{solicitud.id}")
                
                # Descontar stock si corresponde (solo si afecta stock)
                resultado_descuento = descontar_stock_despachado(solicitud)
                logger.info(f"Resultado descuento stock desde edición solicitud #{solicitud.id}: {resultado_descuento}")
                
                # Mensajes informativos
                if bultos_actualizados > 0:
                    messages.info(request, f'{bultos_actualizados} bulto(s) finalizado(s) automáticamente.')
                
                if resultado_descuento.get('descontados', 0) > 0:
                    messages.info(request, f"Se descontaron {resultado_descuento['descontados']} productos de bodega 013.")
                
                print(f"\n{'='*60}")
                print(f"✅ DESPACHO PROCESADO EXITOSAMENTE DESDE EDICIÓN")
                print(f"   Bultos actualizados: {bultos_actualizados}/{total_bultos}")
                print(f"   Productos descontados: {resultado_descuento.get('descontados', 0)}")
                print(f"{'='*60}\n")
            
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
    Si el nuevo estado es 'despachado', actualiza bultos asociados y descuenta el stock.
    """
    from .services import descontar_stock_despachado
    from django.utils import timezone
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
    
    # Si el nuevo estado es despachado, actualizar bultos asociados y descontar stock
    resultado_descuento = None
    bultos_actualizados = 0
    
    # LÓGICA SIMPLE: Si la solicitud pasa a 'despachado', buscar TODOS los bultos asociados y finalizarlos
    if nuevo_estado == 'despachado':
        print(f"\n{'='*60}")
        print(f"🚚 PROCESANDO DESPACHO - Solicitud #{solicitud.id}")
        print(f"{'='*60}")
        print(f"   Afecta stock: {solicitud.afecta_stock}")
        print(f"   Estado anterior: {estado_anterior}")
        print(f"   Nuevo estado: {nuevo_estado}")
        
        # SOLO procesar si cambió el estado (evitar procesar múltiples veces)
        if estado_anterior != 'despachado':
            from despacho.models import Bulto
            
            # BUSCAR TODOS los bultos asociados a esta solicitud
            bultos_asociados = Bulto.objects.filter(solicitud=solicitud)
            total_bultos = bultos_asociados.count()
            
            print(f"\n📦 ACTUALIZACIÓN DE BULTOS:")
            print(f"   Bultos encontrados: {total_bultos}")
            logger.info(f"Buscando bultos para solicitud #{solicitud.id}. Total: {total_bultos}")
            
            if total_bultos > 0:
                # ACTUALIZAR DIRECTAMENTE todos los bultos a 'finalizado' y establecer fechas si faltan
                ahora = timezone.now()
                
                for bulto in bultos_asociados:
                    estado_anterior_bulto = bulto.estado
                    print(f"\n   📦 Bulto {bulto.codigo}:")
                    print(f"      Estado anterior: '{estado_anterior_bulto}'")
                    
                    # SIEMPRE actualizar a 'finalizado' cuando la solicitud está despachada
                    bulto.estado = 'finalizado'
                    campos_actualizar = ['estado']
                    
                    # Establecer fechas si no existen
                    if not bulto.fecha_entrega:
                        bulto.fecha_entrega = ahora
                        campos_actualizar.append('fecha_entrega')
                        print(f"      ✅ Fecha entrega establecida: {bulto.fecha_entrega}")
                    
                    if not bulto.fecha_envio:
                        bulto.fecha_envio = ahora
                        campos_actualizar.append('fecha_envio')
                        print(f"      ✅ Fecha envío establecida: {bulto.fecha_envio}")
                    
                    try:
                        bulto.save(update_fields=campos_actualizar)
                        bultos_actualizados += 1
                        print(f"      ✅ Bulto actualizado a 'finalizado'")
                        logger.info(f"Bulto {bulto.codigo} actualizado a 'finalizado' para solicitud #{solicitud.id}")
                    except Exception as e:
                        print(f"      ❌ ERROR al guardar bulto: {e}")
                        logger.error(f"Error al actualizar bulto {bulto.codigo}: {e}", exc_info=True)
            else:
                print(f"   ⚠️  ADVERTENCIA: No se encontraron bultos asociados a la solicitud")
                logger.warning(f"No se encontraron bultos para solicitud #{solicitud.id}")
            
            # Actualizar detalles que tienen bulto asignado (marcarlos como 'preparado' que es el estado final)
            # Nota: Los detalles no tienen un estado 'despachado', así que los mantenemos en 'preparado'
            print(f"\n📋 ACTUALIZACIÓN DE DETALLES:")
            detalles_con_bulto = solicitud.detalles.filter(bulto__isnull=False)
            total_detalles_con_bulto = detalles_con_bulto.count()
            print(f"   Detalles con bulto asignado: {total_detalles_con_bulto}")
            logger.info(f"Actualizando detalles con bulto para solicitud #{solicitud.id}. Total: {total_detalles_con_bulto}")
            
            if total_detalles_con_bulto > 0:
                detalles_actualizados = detalles_con_bulto.exclude(estado_bodega='preparado').update(estado_bodega='preparado')
                if detalles_actualizados > 0:
                    print(f"   ✅ {detalles_actualizados} detalles actualizados a 'preparado'")
                    logger.info(f"{detalles_actualizados} detalles actualizados a 'preparado' para solicitud #{solicitud.id}")
                else:
                    print(f"   ℹ️  Todos los detalles ya estaban en estado 'preparado'")
                    logger.info(f"Todos los detalles ya estaban 'preparado' para solicitud #{solicitud.id}")
            
            # Descontar stock
            print(f"\n💰 DESCUENTO DE STOCK:")
            print(f"   Afecta stock: {solicitud.afecta_stock}")
            logger.info(f"Ejecutando descuento de stock para solicitud #{solicitud.id}. Afecta stock: {solicitud.afecta_stock}")
            
            resultado_descuento = descontar_stock_despachado(solicitud)
            
            print(f"   Resultado: {resultado_descuento.get('message', 'N/A')}")
            print(f"   Productos descontados: {resultado_descuento.get('descontados', 0)}")
            
            if resultado_descuento.get('errores'):
                print(f"   ⚠️  Errores encontrados: {resultado_descuento['errores']}")
            
            logger.info(f"Resultado descuento stock solicitud #{solicitud.id}: {resultado_descuento}")
            
            if not resultado_descuento['success']:
                mensaje = f'Solicitud marcada como despachada, pero hubo errores al descontar stock: {resultado_descuento.get("errores", [])}'
                print(f"\n   ❌ ERROR EN DESCUENTO DE STOCK")
                logger.error(f"Error al descontar stock para solicitud #{solicitud.id}: {resultado_descuento.get('errores', [])}")
                return JsonResponse({
                    'success': True,
                    'warning': True,
                    'message': mensaje,
                    'descuento': resultado_descuento
                })
            
            print(f"\n{'='*60}")
            print(f"✅ DESPACHO PROCESADO EXITOSAMENTE")
            print(f"   Bultos actualizados: {bultos_actualizados}/{total_bultos}")
            print(f"   Productos descontados: {resultado_descuento.get('descontados', 0)}")
            print(f"{'='*60}\n")
        else:
            logger.info(f"Solicitud #{solicitud.id} ya estaba despachada, omitiendo procesamiento adicional")
    
    mensaje = f'Estado cambiado a {solicitud.get_estado_display()}'
    if numero_guia_despacho:
        mensaje += f' (Guía/Factura: {numero_guia_despacho})'
    if bultos_actualizados > 0:
        mensaje += f'. {bultos_actualizados} bulto(s) actualizado(s) a finalizado.'
    if resultado_descuento and resultado_descuento.get('descontados', 0) > 0:
        mensaje += f' Se descontaron {resultado_descuento["descontados"]} productos de bodega 013.'
    elif nuevo_estado == 'despachado' and not resultado_descuento:
        mensaje += ' (Ya estaba despachada, sin cambios en stock)'
    
    print(f"\n✅ CAMBIO EXITOSO:")
    print(f"   Estado: {estado_anterior} → {nuevo_estado}")
    print(f"   Bultos actualizados: {bultos_actualizados}")
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