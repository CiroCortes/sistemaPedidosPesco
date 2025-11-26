"""
Servidor MCP para Sistema PESCO.

Este servidor expone herramientas que pueden ser usadas por un agente IA
(por ejemplo Gemini 2.5) a través del protocolo Model Context Protocol (MCP).

Requisitos:
    pip install mcp django

Ejecución:
    IA_API_TOKEN=tu-token-secreto \\
    python mcp_server.py

Luego configuras tu cliente MCP (por ejemplo en la herramienta que use Gemini)
para ejecutar este binario por stdio.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict

import django
from mcp.server import Server
from mcp.server.stdio import stdio_server

# ========================
# Inicializar Django
# ========================

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from solicitudes.services import (  # noqa: E402
    SolicitudServiceError,
    crear_solicitud_desde_payload,
)

User = get_user_model()


server = Server("sistema-pesco")


def _get_default_user() -> User | None:
    """
    Intenta obtener un usuario por defecto para asociar a las solicitudes
    creadas por IA. Si no existe, retorna None y se creará con solicitante null.
    """
    try:
        # Puedes cambiar 'admin' por otro usuario de tu preferencia
        return User.objects.filter(is_superuser=True).first() or User.objects.first()
    except Exception:
        return None


@server.tool()
async def ping() -> str:
    """
    Verificación sencilla de que el servidor MCP está vivo.
    Útil para pruebas de conexión desde el cliente IA.
    """
    return "Sistema PESCO MCP server operativo."


@server.tool()
async def crear_solicitud(payload_json: str) -> str:
    """
    Crea una solicitud en el sistema PESCO a partir de un JSON.

    Parámetros:
        payload_json: str
            Cadena JSON con la misma estructura que espera
            `crear_solicitud_desde_payload` en `solicitudes.services`.

    Ejemplo de payload:
        {
          "tipo": "PC",
          "numero_pedido": "25111045",
          "cliente": "SUC LOS ANGELES",
          "bodega": "013-01",
          "transporte": "Camión PESCO",
          "estado": "pendiente",
          "urgente": false,
          "observacion": "Pedido generado por IA",
          "productos": [
            {"codigo": "3502040", "descripcion": "CILINDRO", "cantidad": 5},
            {"codigo": "3502021", "descripcion": "VALVULA", "cantidad": 2}
          ]
        }

    Retorna:
        Un JSON (str) con información básica de la solicitud creada.
    """
    try:
        data: Dict[str, Any] = json.loads(payload_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"payload_json no es un JSON válido: {e}") from e

    solicitante = _get_default_user()

    try:
        solicitud = crear_solicitud_desde_payload(data, solicitante=solicitante)
    except SolicitudServiceError as e:
        # Error de negocio controlado
        return json.dumps({"ok": False, "error": str(e)})
    except Exception as e:
        # Error inesperado
        return json.dumps({"ok": False, "error": f"Error interno: {e}"})

    respuesta = {
        "ok": True,
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
    return json.dumps(respuesta)


async def main() -> None:
    """
    Punto de entrada principal del servidor MCP usando stdio.

    Este patrón es el que esperan los clientes MCP (como editores o agentes IA)
    para comunicarse por stdin/stdout.
    """
    async with stdio_server() as (read, write):
        await server.run(read, write)


if __name__ == "__main__":
    asyncio.run(main())


