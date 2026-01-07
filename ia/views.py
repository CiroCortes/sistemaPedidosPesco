from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.safestring import mark_safe

from solicitudes.services import crear_solicitud_desde_payload, SolicitudServiceError
from .gemini_client import call_gemini_for_solicitud
from .excel_processor import procesar_excel_productos, ExcelProcessorError


@login_required
def ia_chat(request: HttpRequest) -> HttpResponse:
    """
    Asistente IA interno.

    Flujo:
      - Usuario pega texto del correo y/o adjunta imagen (screenshot SAP).
      - NUEVO: Usuario puede adjuntar Excel con códigos masivos.
      - Se llama a Gemini para extraer metadata (tipo, cliente, etc.).
      - Si hay Excel, se extraen los productos del Excel en lugar del texto.
      - Se crea la Solicitud usando crear_solicitud_desde_payload.
    """
    contexto: Dict[str, Any] = {}

    if request.method == "POST":
        texto = request.POST.get("mensaje", "").strip()
        imagen_archivo = request.FILES.get("imagen")
        excel_archivo = request.FILES.get("excel")  # NUEVO
        sin_validacion_stock = request.POST.get("sin_validacion_stock") == "1"  # NUEVO

        if not texto and not imagen_archivo and not excel_archivo:
            messages.error(request, "Debes ingresar texto, adjuntar una imagen o un archivo Excel.")
            return redirect("ia_chat")

        # Procesar Excel si existe
        productos_excel = None
        if excel_archivo:
            try:
                excel_bytes = excel_archivo.read()
                productos_excel = procesar_excel_productos(
                    excel_bytes, 
                    sin_validacion_stock=sin_validacion_stock
                )
                
                if sin_validacion_stock:
                    messages.info(
                        request,
                        f"✅ Excel procesado: {len(productos_excel)} productos detectados (sin validación de stock)."
                    )
                else:
                    messages.info(
                        request,
                        f"✅ Excel procesado: {len(productos_excel)} productos detectados."
                    )
            except ExcelProcessorError as e:
                messages.error(request, f"Error al procesar Excel: {e}")
                return render(request, "ia/chat.html", contexto)

        # Procesar imagen si existe
        image_bytes: Optional[bytes] = None
        if imagen_archivo:
            image_bytes = imagen_archivo.read()

        # Llamar a Gemini para extraer metadata
        try:
            payload = call_gemini_for_solicitud(texto, image_bytes=image_bytes)
            contexto["payload"] = payload
        except Exception as e:
            messages.error(
                request,
                f"Error al procesar con Gemini: {e}",
            )
            return render(request, "ia/chat.html", contexto)

        # Si hay productos del Excel, reemplazar los del payload
        if productos_excel:
            payload["productos"] = productos_excel
            if sin_validacion_stock:
                messages.info(
                    request,
                    f"ℹ️ Usando {len(productos_excel)} productos del archivo Excel (sin validación de stock)."
                )
            else:
                messages.info(
                    request,
                    f"ℹ️ Usando {len(productos_excel)} productos del archivo Excel."
                )
        # Si NO hay productos del Excel, enriquecer los productos del payload de Gemini
        elif payload.get("productos"):
            from .excel_processor import _enriquecer_con_inventario
            print(f"\n🔍 Enriqueciendo {len(payload['productos'])} productos desde Gemini...")
            if sin_validacion_stock:
                print(f"   🔓 Modo: Sin validación de stock activado")
            productos_gemini = payload["productos"]
            productos_enriquecidos = _enriquecer_con_inventario(
                productos_gemini, 
                [],
                sin_validacion_stock=sin_validacion_stock
            )
            payload["productos"] = productos_enriquecidos
            
            # Logging para debugging
            for prod in productos_enriquecidos:
                if prod.get('_bodega_auto'):
                    print(f"   ✅ {prod['codigo']}: Bodega {prod['bodega']} (Stock: {prod.get('_stock_disponible', 'N/A')})")
                    if prod.get('_bodegas_alternativas'):
                        print(f"      Alternativas: {', '.join(prod['_bodegas_alternativas'])}")
                elif prod.get('_sin_stock'):
                    bodega_info = f"Bodega {prod.get('bodega', 'N/A')}" if prod.get('bodega') else "Sin bodega"
                    print(f"   ⚠️  {prod['codigo']}: Sin stock - {bodega_info}")
                else:
                    print(f"   ℹ️  {prod['codigo']}: Bodega {prod.get('bodega', 'N/A')} (manual)")

        # Crear solicitud
        try:
            solicitud = crear_solicitud_desde_payload(payload, solicitante=request.user)
            
            # Información detallada de bodegas asignadas
            detalles = solicitud.detalles.all()
            bodegas_asignadas = {}
            sin_bodega = 0
            
            for det in detalles:
                if det.bodega:
                    if det.bodega not in bodegas_asignadas:
                        bodegas_asignadas[det.bodega] = 0
                    bodegas_asignadas[det.bodega] += 1
                else:
                    sin_bodega += 1
            
            # Construir mensaje de éxito con detalle de bodegas
            mensaje = f"✅ Solicitud #{solicitud.id} creada por IA con {solicitud.total_codigos()} productos."
            
            if bodegas_asignadas:
                mensaje += "<br><strong>Bodegas asignadas automáticamente:</strong>"
                for bodega, count in bodegas_asignadas.items():
                    mensaje += f"<br>📦 Bodega {bodega}: {count} producto(s)"
            
            if sin_bodega > 0:
                mensaje += f"<br>⚠️ {sin_bodega} producto(s) sin stock (orden especial)"
            
            messages.success(request, mark_safe(mensaje))
            
        except SolicitudServiceError as e:
            messages.error(request, f"Error al crear la solicitud: {e}")
            return render(request, "ia/chat.html", contexto)
        except Exception as e:
            messages.error(request, f"Error interno al crear la solicitud: {e}")
            return render(request, "ia/chat.html", contexto)

        return redirect("solicitudes:detalle", pk=solicitud.id)

    return render(request, "ia/chat.html", contexto)

