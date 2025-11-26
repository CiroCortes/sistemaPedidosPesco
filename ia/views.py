from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from solicitudes.services import crear_solicitud_desde_payload, SolicitudServiceError
from .gemini_client import call_gemini_for_solicitud


@login_required
def ia_chat(request: HttpRequest) -> HttpResponse:
    """
    Asistente IA interno.

    Flujo:
      - Usuario pega texto del correo y/o adjunta imagen (screenshot SAP).
      - Se llama a Gemini para extraer un payload estructurado.
      - Se crea la Solicitud usando crear_solicitud_desde_payload.
    """
    contexto: Dict[str, Any] = {}

    if request.method == "POST":
        texto = request.POST.get("mensaje", "").strip()
        imagen_archivo = request.FILES.get("imagen")

        if not texto and not imagen_archivo:
            messages.error(request, "Debes ingresar texto o adjuntar una imagen.")
            return redirect("ia_chat")

        image_bytes: Optional[bytes] = None
        if imagen_archivo:
            image_bytes = imagen_archivo.read()

        try:
            payload = call_gemini_for_solicitud(texto, image_bytes=image_bytes)
            contexto["payload"] = payload
        except Exception as e:
            messages.error(
                request,
                f"Error al procesar con Gemini: {e}",
            )
            return render(request, "ia/chat.html", contexto)

        try:
            solicitud = crear_solicitud_desde_payload(payload, solicitante=request.user)
        except SolicitudServiceError as e:
            messages.error(request, f"Error al crear la solicitud: {e}")
            return render(request, "ia/chat.html", contexto)
        except Exception as e:
            messages.error(request, f"Error interno al crear la solicitud: {e}")
            return render(request, "ia/chat.html", contexto)

        messages.success(
            request,
            f"Solicitud #{solicitud.id} creada correctamente por IA.",
        )
        return redirect("solicitudes:detalle", pk=solicitud.id)

    return render(request, "ia/chat.html", contexto)


