"""
Cliente simple para llamar a Gemini 2.5 desde el backend de PESCO.

NOTA IMPORTANTE:
- Este módulo asume que tienes instalada la librería:
    pip install google-generativeai
- Y que tienes configurada la variable de entorno:
    GEMINI_API_KEY=tu_api_key

Este código no se ejecuta automáticamente; se usará desde vistas
cuando quieras habilitar la IA dentro del proyecto.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import json
import os


def call_gemini_for_solicitud(
    texto: str,
    image_bytes: Optional[bytes] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envía texto (y opcionalmente una imagen) a Gemini y espera un JSON
    con el payload de solicitud en el formato esperado por
    `crear_solicitud_desde_payload`.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada en las variables de entorno.")

    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "Falta la librería 'google-generativeai'. "
            "Instala con: pip install google-generativeai"
        ) from e

    genai.configure(api_key=api_key)

    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(model_name)

    system_prompt = (
        "Eres un asistente para un sistema logístico PESCO.\n"
        "Tu prioridad ABSOLUTA es extraer correctamente los productos (códigos y cantidades) "
        "desde correos o pantallazos de SAP.\n"
        "Debes devolver UNICAMENTE un JSON válido, sin comentarios ni texto adicional, "
        "con este formato:\n\n"
        "{\n"
        '  "tipo": "PC|OF|EM|RM|ST",\n'
        '  "numero_pedido": "string o vacío",\n'
        '  "cliente": "string",\n'
        '  "bodega": "",\n'
        '  "transporte": "Camión PESCO|Varmontt|Starken|Kaizen|Retira cliente|Otro",\n'
        '  "estado": "pendiente",\n'
        '  "urgente": true/false,\n'
        '  "observacion": "string",\n'
        '  "productos": [\n'
        '     {"codigo": "SC o código", "descripcion": "string (opcional)", "cantidad": numero_entero_positivo}\n'
        "  ]\n"
        "}\n\n"
        "REGLAS IMPORTANTES:\n"
        "- El campo \"bodega\" en la cabecera debe estar SIEMPRE VACÍO (\"\"). El sistema asignará automáticamente.\n"
        "- En \"productos\", NO incluyas el campo \"bodega\". El sistema lo asignará automáticamente según disponibilidad.\n"
        "- La \"descripcion\" en productos es OPCIONAL. Si no la ves claramente, déjala vacía. El sistema la buscará en Stock.\n"
        "- En el campo \"observacion\" debes copiar cualquier instrucción adicional del correo, "
        "por ejemplo: textos como 'cargar costo a la Orden de Facturación N° ...', "
        "'entregar en dirección ...', notas especiales, etc.\n"
        "- Usa \"SC\" como código SOLO cuando realmente no exista código de producto en el texto o imagen.\n"
        "- Para pedidos PC/OF/EM, si ves un número de pedido (por ejemplo 'PC 30504578' o 'Código 30504578'), "
        "debes colocarlo en \"numero_pedido\".\n"
        "- Para traslados ST: normalmente no viene un número de pedido; en ese caso deja \"numero_pedido\" vacío "
        "y el sistema generará un número ST automático. No inventes números de pedido para ST.\n"
        "- Nunca inventes productos ni cantidades; solo incluye los que veas explícitamente.\n"
        "- El \"estado\" debe ser siempre \"pendiente\" para solicitudes nuevas.\n"
    )

    contents: list[Any] = [system_prompt, texto]
    if image_bytes:
        # google-generativeai acepta imagen como dict con mime_type + data
        contents.append(
            {
                "mime_type": "image/png",
                "data": image_bytes,
            }
        )

    response = model.generate_content(contents)
    raw = response.text or ""

    # Asegurarse de extraer solo el JSON (por si el modelo agrega texto)
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"Gemini no devolvió un JSON reconocible: {raw}")

    json_str = raw[start : end + 1]
    data = json.loads(json_str)
    return data


