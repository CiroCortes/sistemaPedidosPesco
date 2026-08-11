"""
Cliente para llamar a Claude (vía AWS Bedrock) desde el backend de PESCO.

Reemplaza al antiguo cliente de Gemini. Usa el rol de IAM de la instancia
(EC2/App Runner) para autenticarse - no requiere API key.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import json
import os

import boto3

MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _client


SYSTEM_PROMPT = (
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


def call_bedrock_for_solicitud(
    texto: str,
    image_bytes: Optional[bytes] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Envía texto (y opcionalmente una imagen) a Claude vía Bedrock y espera un JSON
    con el payload de solicitud en el formato esperado por
    `crear_solicitud_desde_payload`.
    """
    client = _get_client()

    content: list[Dict[str, Any]] = [{"text": texto or "(sin texto, ver imagen adjunta)"}]
    if image_bytes:
        content.append(
            {
                "image": {
                    "format": "png",
                    "source": {"bytes": image_bytes},
                }
            }
        )

    response = client.converse(
        modelId=model_id or MODEL_ID,
        system=[{"text": SYSTEM_PROMPT}],
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 2048, "temperature": 0},
    )

    raw = response["output"]["message"]["content"][0]["text"] or ""
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"Bedrock no devolvió un JSON reconocible: {raw}")

    json_str = raw[start : end + 1]
    data = json.loads(json_str)
    return data
