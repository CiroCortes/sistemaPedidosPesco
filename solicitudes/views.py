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
from .forms import SolicitudForm, SolicitudDetalleFormSet
from .models import Solicitud
from .services import crear_solicitud_desde_payload, SolicitudServiceError


@login_required
def lista_solicitudes(request):
    """
    Vista principal del módulo de solicitudes.
    Aplica filtros según rol y parámetros del usuario.
    """
    user = request.user
    solicitudes = (
        Solicitud.objects
        .select_related('solicitante')
        .prefetch_related('detalles')
        .order_by('id')  # Ordenar de menor a mayor por ID
    )

    # Restricciones por rol
    if user.es_bodega():
        solicitudes = solicitudes.filter(estado='pendiente')
    elif user.es_despacho():
        solicitudes = solicitudes.filter(estado__in=['en_despacho', 'embalado'])

    # Filtros desde la URL
    estado = request.GET.get('estado', '')
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
        )

    paginator = Paginator(solicitudes, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    stats = Solicitud.objects.values('estado').annotate(total=Count('id'))

    context = {
        'page_obj': page_obj,
        'estado': estado,
        'tipo': tipo,
        'urgente': urgente,
        'busqueda': busqueda,
        'stats': stats,
        'es_admin': user.es_admin(),
        'tipos': Solicitud.TIPOS,
        'estados': Solicitud.ESTADOS,
    }
    return render(request, 'solicitudes/lista.html', context)


@login_required
@role_required(['admin'])
def crear_solicitud(request):
    """
    Permite al admin registrar nuevas solicitudes.
    """
    if request.method == 'POST':
        form = SolicitudForm(request.POST)
        formset = SolicitudDetalleFormSet(request.POST, prefix='detalles')
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
                    )

                messages.success(request, f'Solicitud #{solicitud.id} creada correctamente.')
                return redirect('solicitudes:lista')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = SolicitudForm()
        formset = SolicitudDetalleFormSet(prefix='detalles')

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
    if request.user.es_despacho() and solicitud.estado not in ['en_despacho', 'embalado']:
        messages.warning(request, 'No puedes acceder a solicitudes fuera de tu módulo.')
        return redirect('solicitudes:lista')

    detalles = solicitud.detalles.all()
    return render(request, 'solicitudes/detalle.html', {'solicitud': solicitud, 'detalles': detalles})


@login_required
def detalle_solicitud_ajax(request, pk):
    """
    Endpoint AJAX para obtener el detalle de una solicitud en formato JSON.
    Usado por el modal de vista rápida.
    """
    try:
        solicitud = Solicitud.objects.select_related('solicitante').prefetch_related('detalles').get(pk=pk)
        
        # Validación de acceso
        if request.user.es_bodega() and solicitud.estado != 'pendiente':
            return JsonResponse({'error': 'No tienes acceso a esta solicitud'}, status=403)
        if request.user.es_despacho() and solicitud.estado not in ['en_despacho', 'embalado']:
            return JsonResponse({'error': 'No tienes acceso a esta solicitud'}, status=403)
        
        # Preparar datos de productos
        productos = []
        detalles = solicitud.detalles.all()
        
        if detalles.exists():
            # Solicitud nueva con tabla de detalles
            for det in detalles:
                productos.append({
                    'codigo': det.codigo,
                    'descripcion': det.descripcion,
                    'cantidad': det.cantidad
                })
        else:
            # Solicitud antigua sin detalles
            productos.append({
                'codigo': solicitud.codigo,
                'descripcion': solicitud.descripcion,
                'cantidad': solicitud.cantidad_solicitada
            })
        
        # Preparar respuesta
        data = {
            'id': solicitud.id,
            'fecha': solicitud.fecha_solicitud.strftime('%d/%m/%Y'),
            'hora': solicitud.hora_solicitud.strftime('%H:%M'),
            'tipo': solicitud.get_tipo_display(),
            'numero_pedido': solicitud.numero_pedido or '-',
            'numero_st': solicitud.numero_st or '-',
            'cliente': solicitud.cliente,
            'bodega': solicitud.bodega or '-',
            'transporte': solicitud.get_transporte_display(),
            'estado': solicitud.get_estado_display(),
            'color_estado': solicitud.color_estado(),  # Llamar al método
            'urgente': solicitud.urgente,
            'descripcion': solicitud.descripcion or '-',
            'observacion': solicitud.observacion or 'Sin observaciones',
            'solicitante': solicitud.solicitante.nombre_completo if solicitud.solicitante and solicitud.solicitante.nombre_completo else (solicitud.solicitante.username if solicitud.solicitante else 'Sistema'),
            'created_at': solicitud.created_at.strftime('%d/%m/%Y %H:%M'),
            'updated_at': solicitud.updated_at.strftime('%d/%m/%Y %H:%M'),
            'productos': productos
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
        "numero_st": solicitud.numero_st,
        "cliente": solicitud.cliente,
        "bodega": solicitud.bodega,
        "transporte": solicitud.get_transporte_display(),
        "estado": solicitud.estado,
        "urgente": solicitud.urgente,
        "created_at": solicitud.created_at.isoformat(),
    }
    return JsonResponse(response, status=201)
