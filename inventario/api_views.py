from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import StockSAP
from .services import StockService
from django.db.models import Sum


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_producto(request, codigo):
    """
    GET /inventario/api/stock/{codigo}/
    
    Retorna stock de un producto en todas las bodegas.
    """
    stock_items = StockSAP.objects.filter(codigo=codigo)
    
    if not stock_items.exists():
        return Response({
            'error': 'Producto no encontrado',
            'codigo': codigo
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Calcular totales
    total_stock = stock_items.aggregate(total=Sum('stock_disponible'))['total'] or 0
    total_valor = stock_items.aggregate(total=Sum('total'))['total'] or 0
    
    # Desglose por bodega
    bodegas = []
    for item in stock_items:
        bodegas.append({
            'codigo_bodega': item.bodega,
            'nombre_bodega': item.bodega_nombre,
            'stock': item.stock_disponible,
            'ubicacion': item.ubicacion,
            'precio_unitario': float(item.precio) if item.precio else None,
            'valor_total': float(item.total) if item.total else None,
        })
    
    return Response({
        'codigo': codigo,
        'descripcion': stock_items.first().descripcion,
        'stock_total': int(total_stock),
        'valor_total': float(total_valor) if total_valor else None,
        'cantidad_bodegas': len(bodegas),
        'bodegas': bodegas
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verificar_disponibilidad(request):
    """
    POST /inventario/api/stock/verificar-disponibilidad/
    
    Body: {
        "items": [
            {"codigo": "10105006", "cantidad": 50},
            {"codigo": "10105009", "cantidad": 100}
        ]
    }
    
    Retorna disponibilidad de múltiples productos.
    """
    items = request.data.get('items', [])
    
    if not items:
        return Response({
            'error': 'Debe enviar lista de items en el campo "items"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    resultados = []
    
    for item in items:
        codigo = item.get('codigo')
        cantidad_solicitada = int(item.get('cantidad', 0))
        
        # Obtener stock total (suma de todas las bodegas)
        stock_total = StockSAP.objects.filter(codigo=codigo).aggregate(
            total=Sum('stock_disponible')
        )['total'] or 0
        
        disponible = stock_total >= cantidad_solicitada
        
        resultados.append({
            'codigo': codigo,
            'cantidad_solicitada': cantidad_solicitada,
            'stock_disponible': int(stock_total),
            'disponible': disponible,
            'faltante': max(0, cantidad_solicitada - stock_total)
        })
    
    return Response({
        'items': resultados,
        'todos_disponibles': all(r['disponible'] for r in resultados)
    })
