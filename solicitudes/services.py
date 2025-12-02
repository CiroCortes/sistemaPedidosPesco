"""
Servicios de alto nivel para el módulo de Solicitudes.

La idea es que tanto las vistas Django como futuros agentes (MCP, IA, etc.)
puedan reutilizar la misma lógica de negocio sin duplicar código.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from django.contrib.auth import get_user_model
from django.db import transaction

from configuracion.models import TransporteConfig
from .models import Solicitud, SolicitudDetalle


User = get_user_model()


def descontar_stock_despachado(solicitud: Solicitud) -> Dict[str, Any]:
    """
    Descuenta el stock de bodega 013 cuando una solicitud se marca como despachada.
    Solo descuenta los detalles que tienen bulto_id asignado (que efectivamente salieron).
    
    Retorna un diccionario con información del descuento realizado.
    """
    from bodega.models import Stock
    
    # Si la solicitud no afecta stock, no hacer nada
    if not solicitud.afecta_stock:
        return {
            'success': True,
            'descontados': 0,
            'message': 'Solicitud no afecta stock (orden especial)'
        }
    
    # Obtener detalles que salieron (tienen bulto asignado)
    detalles_despachados = solicitud.detalles.filter(bulto__isnull=False)
    
    if not detalles_despachados.exists():
        return {
            'success': True,
            'descontados': 0,
            'message': 'No hay productos despachados en bultos'
        }
    
    descontados = []
    errores = []
    
    with transaction.atomic():
        for detalle in detalles_despachados:
            try:
                stock_013 = Stock.objects.filter(
                    codigo=detalle.codigo,
                    bodega='013'
                ).first()
                
                if stock_013:
                    stock_anterior = stock_013.stock_disponible
                    stock_013.stock_disponible = max(0, stock_013.stock_disponible - detalle.cantidad)
                    stock_013.save(update_fields=['stock_disponible'])
                    
                    descontados.append({
                        'codigo': detalle.codigo,
                        'cantidad': detalle.cantidad,
                        'stock_anterior': stock_anterior,
                        'stock_nuevo': stock_013.stock_disponible,
                        'bulto': detalle.bulto.codigo if detalle.bulto else None
                    })
                else:
                    # No hay registro en bodega 013, puede ser normal si nunca se transfirió
                    errores.append({
                        'codigo': detalle.codigo,
                        'mensaje': 'No existe en bodega 013'
                    })
            except Exception as e:
                errores.append({
                    'codigo': detalle.codigo,
                    'mensaje': str(e)
                })
    
    return {
        'success': len(errores) == 0,
        'descontados': len(descontados),
        'detalles': descontados,
        'errores': errores,
        'message': f'Se descontaron {len(descontados)} productos de bodega 013'
    }


class SolicitudServiceError(Exception):
    """Error controlado en la creación de solicitudes."""


def _normalizar_transporte(valor: str) -> str:
    """
    Normaliza la entrada de transporte utilizando la configuración dinámica.
    """
    activos = list(TransporteConfig.activos())
    default_slug = activos[0].slug if activos else "PESCO"

    if not valor:
        return default_slug

    valor_norm = valor.strip()

    slug_match = next((t.slug for t in activos if t.slug.lower() == valor_norm.lower()), None)
    if slug_match:
        return slug_match

    nombre_match = next((t.slug for t in activos if t.nombre.lower() == valor_norm.lower()), None)
    if nombre_match:
        return nombre_match

    return default_slug


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
        "listo": "listo_despacho",
        "listo_despacho": "listo_despacho",
        "listo para despacho": "listo_despacho",
        "en_ruta": "en_ruta",
        "en ruta": "en_ruta",
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
    numero_ot = (payload.get("numero_ot") or "").strip()
    cliente = (payload.get("cliente") or "").strip()
    # La bodega en cabecera se ignora o se usa como fallback si se desea, 
    # pero el modelo ya no la requiere obligatoriamente si la quitamos.
    # Por ahora la leemos pero no la usaremos en el modelo Solicitud si lo hemos quitado.
    # Sin embargo, el modelo Solicitud todavía tiene el campo bodega en la definición original?
    # No, en el plan dijimos que lo eliminaríamos. Pero en la fase 1 solo agregamos a detalle.
    # Si no lo hemos eliminado de Solicitud, debemos seguir pasándolo.
    # Asumimos que sigue existiendo en Solicitud por compatibilidad o migración gradual.
    bodega_cabecera = (payload.get("bodega") or "").strip()
    
    transporte = _normalizar_transporte(payload.get("transporte"))
    observacion = payload.get("observacion") or ""
    estado = _normalizar_estado(payload.get("estado"))
    urgente = bool(payload.get("urgente", False))

    if not cliente:
        raise SolicitudServiceError("El cliente es obligatorio.")

    productos: Iterable[Dict[str, Any]] = payload.get("productos") or []
    productos_validos = []
    for prod in productos:
        codigo = (prod.get("codigo") or "").strip()
        descripcion = (prod.get("descripcion") or "").strip()
        cantidad = int(prod.get("cantidad") or 0)
        bodega_prod = (prod.get("bodega") or "").strip()
        
        if not codigo and not descripcion and cantidad <= 0:
            continue
        if cantidad <= 0:
            raise SolicitudServiceError(
                f"La cantidad debe ser > 0 para el producto {codigo or descripcion!r}."
            )
        productos_validos.append(
            {
                "codigo": codigo or "SC", 
                "descripcion": descripcion, 
                "cantidad": cantidad,
                "bodega": bodega_prod
            }
        )

    if not productos_validos:
        raise SolicitudServiceError("Debe haber al menos un producto en 'productos'.")

    primera = productos_validos[0]

    solicitud = Solicitud(
        tipo=tipo,
        numero_pedido=numero_pedido,
        cliente=cliente,
        bodega=bodega_cabecera, # Mantenemos compatibilidad si el campo existe
        transporte=transporte,
        observacion=observacion,
        numero_ot=numero_ot,
        estado=estado,
        urgente=urgente,
        codigo=primera["codigo"],
        descripcion=primera["descripcion"],
        cantidad_solicitada=primera["cantidad"],
        solicitante=solicitante,
    )
    solicitud.save()

    print(f"\n{'='*60}")
    print(f"📋 SOLICITUD CREADA: #{solicitud.id}")
    print(f"   Cliente: {solicitud.cliente}")
    print(f"   Tipo: {solicitud.get_tipo_display()}")
    print(f"   Productos: {len(productos_validos)}")
    print(f"{'='*60}\n")

    for prod in productos_validos:
        detalle = SolicitudDetalle.objects.create(
            solicitud=solicitud,
            codigo=prod["codigo"],
            descripcion=prod["descripcion"],
            cantidad=prod["cantidad"],
            bodega=prod.get("bodega", ""),
        )
        
        # Logging para ver bodega asignada
        bodega_info = f"Bodega: {prod.get('bodega', 'N/A')}" if prod.get('bodega') else "Sin bodega"
        auto_info = " (auto)" if prod.get('_bodega_auto') else ""
        stock_info = f" - Stock: {prod.get('_stock_disponible', '')}" if prod.get('_stock_disponible') else ""
        print(f"   ✅ {prod['codigo']} x{prod['cantidad']} → {bodega_info}{auto_info}{stock_info}")

    return solicitud
