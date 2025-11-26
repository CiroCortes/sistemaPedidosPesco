"""
Servicios de alto nivel para el módulo de Solicitudes.

La idea es que tanto las vistas Django como futuros agentes (MCP, IA, etc.)
puedan reutilizar la misma lógica de negocio sin duplicar código.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Solicitud


User = get_user_model()


class SolicitudServiceError(Exception):
    """Error controlado en la creación de solicitudes."""


def _normalizar_transporte(valor: str) -> str:
    """
    Normaliza la entrada de transporte a uno de los códigos definidos en el modelo.
    Acepta tanto el código interno como el label mostrado.
    """
    if not valor:
        return "PESCO"

    valor_norm = valor.strip().upper()

    mapping = {
        "CAMIÓN PESCO": "PESCO",
        "CAMION PESCO": "PESCO",
        "PESCO": "PESCO",
        "VARMONTT": "VARMONTT",
        "STARKEN": "STARKEN",
        "KAIZEN": "KAIZEN",
        "RETIRA CLIENTE": "RETIRA_CLIENTE",
        "CLIENTE RETIRA": "RETIRA_CLIENTE",
        "OTRO": "OTRO",
        "OTRO / COORDINADO": "OTRO",
    }

    return mapping.get(valor_norm, "OTRO")


def _normalizar_tipo(valor: str) -> str:
    """
    Normaliza el tipo de solicitud a uno de los códigos definidos en el modelo.
    """
    if not valor:
        raise SolicitudServiceError("El tipo de solicitud es obligatorio.")

    valor_norm = valor.strip().upper()
    aliases = {
        "PC": "PC",
        "PEDIDO CLIENTE": "PC",
        "OF": "OF",
        "ORDEN FABRICACION": "OF",
        "ORDEN DE FABRICACION": "OF",
        "EM": "EM",
        "ENTRADA MERCANCIAS": "EM",
        "ENTRADA DE MERCANCIAS": "EM",
        "RM": "RM",
        "RETIRO MERCANCIAS": "RM",
        "RETIRO DE MERCANCIAS": "RM",
        "ST": "ST",
        "SOLICITUD TRASLADO": "ST",
        "SOLICITUD DE TRASLADO": "ST",
    }

    codigo = aliases.get(valor_norm)
    if not codigo:
        raise SolicitudServiceError(f"Tipo de solicitud no válido: {valor}")
    return codigo


def _normalizar_estado(valor: Optional[str]) -> str:
    """
    Normaliza el estado inicial. Por defecto 'pendiente'.
    """
    if not valor:
        return "pendiente"

    valor_norm = valor.strip().lower()
    mapping = {
        "pendiente": "pendiente",
        "en_despacho": "en_despacho",
        "en despacho": "en_despacho",
        "embalado": "embalado",
        "despachado": "despachado",
        "cancelado": "cancelado",
    }
    return mapping.get(valor_norm, "pendiente")


@transaction.atomic
def crear_solicitud_desde_payload(
    payload: Dict[str, Any],
    solicitante: Optional[User] = None,
) -> Solicitud:
    """
    Crea una Solicitud + detalles a partir de un diccionario de datos.

    Este método está pensado para ser usado por:
    - Vistas Django que reciben JSON
    - Servidores MCP / agentes de IA

    Estructura esperada del payload (ejemplo):
    {
        "tipo": "PC",
        "numero_pedido": "25111045",
        "cliente": "SUC LOS ANGELES",
        "bodega": "013-01",
        "transporte": "Camión PESCO",
        "estado": "pendiente",
        "urgente": false,
        "observacion": "Retira en dirección X",
        "productos": [
            {"codigo": "3502040", "descripcion": "CILINDRO", "cantidad": 5},
            {"codigo": "3502021", "descripcion": "VALVULA", "cantidad": 2}
        ]
    }
    """

    tipo = _normalizar_tipo(payload.get("tipo"))
    numero_pedido = (payload.get("numero_pedido") or "").strip()
    cliente = (payload.get("cliente") or "").strip()
    bodega = (payload.get("bodega") or "").strip()
    transporte = _normalizar_transporte(payload.get("transporte"))
    observacion = payload.get("observacion") or ""
    estado = _normalizar_estado(payload.get("estado"))
    urgente = bool(payload.get("urgente", False))

    if not cliente:
        raise SolicitudServiceError("El cliente es obligatorio.")
    # La bodega puede quedar vacía; el admin o la IA la definirán más adelante.

    productos: Iterable[Dict[str, Any]] = payload.get("productos") or []
    productos_validos = []
    for prod in productos:
        codigo = (prod.get("codigo") or "").strip()
        descripcion = (prod.get("descripcion") or "").strip()
        cantidad = int(prod.get("cantidad") or 0)
        if not codigo and not descripcion and cantidad <= 0:
            continue
        if cantidad <= 0:
            raise SolicitudServiceError(
                f"La cantidad debe ser > 0 para el producto {codigo or descripcion!r}."
            )
        productos_validos.append(
            {"codigo": codigo or "SC", "descripcion": descripcion, "cantidad": cantidad}
        )

    if not productos_validos:
        raise SolicitudServiceError("Debe haber al menos un producto en 'productos'.")

    primera = productos_validos[0]

    solicitud = Solicitud(
        tipo=tipo,
        numero_pedido=numero_pedido,
        cliente=cliente,
        bodega=bodega,
        transporte=transporte,
        observacion=observacion,
        estado=estado,
        urgente=urgente,
        codigo=primera["codigo"],
        descripcion=primera["descripcion"],
        cantidad_solicitada=primera["cantidad"],
        solicitante=solicitante,
    )
    solicitud.save()

    for prod in productos_validos:
        solicitud.detalles.create(
            codigo=prod["codigo"],
            descripcion=prod["descripcion"],
            cantidad=prod["cantidad"],
        )

    return solicitud


