"""
Procesador de archivos Excel para el asistente IA.
Extrae códigos de productos y cantidades de un archivo Excel simple.
"""

from typing import List, Dict, Any
import pandas as pd
from io import BytesIO


class ExcelProcessorError(Exception):
    """Error al procesar archivo Excel"""
    pass


def procesar_excel_productos(archivo_bytes: bytes, enriquecer_con_inventario: bool = True) -> List[Dict[str, Any]]:
    """
    Procesa un archivo Excel y extrae los productos (código y cantidad).
    
    Formatos soportados:
    1. [Código | Cantidad]
    2. [Código | Descripción | Cantidad]
    3. Cualquier Excel que tenga columnas reconocibles
    
    Args:
        archivo_bytes: Contenido del archivo Excel en bytes
        enriquecer_con_inventario: Si True, busca descripciones en StockSAP
        
    Returns:
        Lista de productos: [{"codigo": "123", "cantidad": 10, "descripcion": "..."}, ...]
        
    Raises:
        ExcelProcessorError: Si no se puede procesar el archivo
    """
    try:
        # Leer Excel desde bytes
        df = pd.read_excel(BytesIO(archivo_bytes))
        
        # Validar que no esté vacío
        if df.empty:
            raise ExcelProcessorError("El archivo Excel está vacío")
        
        # Detectar columnas
        columnas = detectar_columnas(df)
        
        # Extraer productos
        productos = []
        codigos_sin_descripcion = []
        
        for idx, row in df.iterrows():
            try:
                codigo = str(row[columnas['codigo']]).strip()
                cantidad = extraer_cantidad(row[columnas['cantidad']])
                
                # Saltar filas vacías
                if not codigo or codigo.lower() in ['nan', 'none', '']:
                    continue
                
                producto = {
                    'codigo': codigo,
                    'cantidad': cantidad
                }
                
                # Agregar descripción si existe en el Excel
                if columnas.get('descripcion'):
                    descripcion = str(row[columnas['descripcion']]).strip()
                    if descripcion and descripcion.lower() not in ['nan', 'none', '']:
                        producto['descripcion'] = descripcion
                    else:
                        codigos_sin_descripcion.append(codigo)
                else:
                    codigos_sin_descripcion.append(codigo)
                
                # Agregar bodega si existe en el Excel
                if columnas.get('bodega'):
                    bodega = str(row[columnas['bodega']]).strip()
                    if bodega and bodega.lower() not in ['nan', 'none', '']:
                        producto['bodega'] = bodega
                
                productos.append(producto)
                
            except Exception as e:
                # Saltar filas con errores pero continuar
                continue
        
        if not productos:
            raise ExcelProcessorError(
                "No se encontraron productos válidos en el archivo. "
                "Verifica que tenga columnas de Código y Cantidad."
            )
        
        # Enriquecer con descripciones y bodegas del inventario
        # SIEMPRE enriquecer para asegurar consistencia
        if enriquecer_con_inventario:
            print(f"\n🔍 Enriqueciendo {len(productos)} productos desde Stock...")
            productos = _enriquecer_con_inventario(productos, codigos_sin_descripcion)
            
            # Logging para debugging
            for prod in productos:
                if prod.get('_bodega_auto'):
                    print(f"   ✅ {prod['codigo']}: Bodega {prod['bodega']} (Stock: {prod.get('_stock_disponible', 'N/A')})")
                    if prod.get('_bodegas_alternativas'):
                        print(f"      Alternativas: {', '.join(prod['_bodegas_alternativas'])}")
                elif prod.get('_sin_stock'):
                    print(f"   ⚠️  {prod['codigo']}: Sin stock disponible (orden especial)")
                else:
                    print(f"   ℹ️  {prod['codigo']}: Bodega {prod.get('bodega', 'N/A')} (manual)")
        
        return productos
        
    except ExcelProcessorError:
        raise
    except Exception as e:
        raise ExcelProcessorError(f"Error al leer el archivo Excel: {str(e)}")


def _enriquecer_con_inventario(productos: List[Dict], codigos_sin_descripcion: List[str]) -> List[Dict]:
    """
    Busca las descripciones y bodegas de los códigos en la tabla Stock.
    SIEMPRE busca en Stock, incluso si ya tiene descripción.
    Asigna la bodega con más stock automáticamente.
    
    Args:
        productos: Lista de productos a enriquecer
        codigos_sin_descripcion: Códigos que necesitan descripción (legacy)
        
    Returns:
        Lista de productos enriquecida con descripciones y bodegas
    """
    try:
        from bodega.models import Stock
        from core.models import Bodega
        
        # Obtener TODOS los códigos únicos de los productos
        todos_codigos = list(set(p['codigo'] for p in productos))
        
        # Consultar Stock para descripciones y bodegas
        stock_items = Stock.objects.filter(
            codigo__in=todos_codigos
        ).values('codigo', 'descripcion', 'bodega', 'bodega_nombre', 'stock_disponible')
        
        # Obtener bodegas activas del sistema
        bodegas_activas = list(Bodega.objects.filter(activa=True).values_list('codigo', flat=True))
        
        # Mapas para búsqueda rápida
        descripciones_map = {}
        bodegas_disponibles_map = {}  # codigo -> lista de bodegas con stock
        
        for item in stock_items:
            codigo = item['codigo']
            
            # Mapa de descripciones (tomar la primera que encuentre no vacía)
            if codigo not in descripciones_map and item['descripcion']:
                descripciones_map[codigo] = item['descripcion']
            
            # Mapa de bodegas con stock (solo bodegas activas)
            if item['stock_disponible'] > 0 and item['bodega'] in bodegas_activas:
                if codigo not in bodegas_disponibles_map:
                    bodegas_disponibles_map[codigo] = []
                bodegas_disponibles_map[codigo].append({
                    'bodega': item['bodega'],
                    'nombre': item['bodega_nombre'] or item['bodega'],
                    'stock': item['stock_disponible']
                })
        
        # Enriquecer TODOS los productos
        for producto in productos:
            codigo = producto['codigo']
            
            # 1. Asignar/Actualizar Descripción SIEMPRE desde Stock
            if codigo in descripciones_map:
                producto['descripcion'] = descripciones_map[codigo]
            elif 'descripcion' not in producto or not producto.get('descripcion'):
                producto['descripcion'] = f"Código: {codigo}"
            
            # 2. Asignar Bodega SIEMPRE si no viene especificada
            if 'bodega' not in producto or not producto.get('bodega'):
                if codigo in bodegas_disponibles_map:
                    # Lógica de asignación: Priorizar bodega con más stock
                    bodegas = bodegas_disponibles_map[codigo]
                    bodegas.sort(key=lambda x: x['stock'], reverse=True)
                    
                    # Asignar la bodega con más stock
                    producto['bodega'] = bodegas[0]['bodega']
                    producto['_bodega_auto'] = True
                    producto['_stock_disponible'] = bodegas[0]['stock']
                    producto['_bodega_nombre'] = bodegas[0]['nombre']
                    
                    # Guardar todas las bodegas disponibles (para logging/debug)
                    producto['_bodegas_alternativas'] = [
                        f"{b['bodega']} ({b['stock']} unids)" for b in bodegas
                    ]
                else:
                    # Si no hay stock en ninguna bodega, dejar vacío
                    # El sistema lo tratará como orden especial
                    producto['bodega'] = ''
                    producto['_sin_stock'] = True
        
        return productos
        
    except ImportError as e:
        print(f"⚠️ Error de importación en _enriquecer_con_inventario: {e}")
        return productos
    except Exception as e:
        print(f"⚠️ Error en _enriquecer_con_inventario: {e}")
        return productos


def detectar_columnas(df: pd.DataFrame) -> Dict[str, str]:
    """
    Detecta automáticamente las columnas de Código, Cantidad y Descripción.
    
    Busca nombres comunes en español e inglés.
    """
    columnas_originales = [str(col).lower() for col in df.columns]
    
    resultado = {}
    
    # Detectar columna de código
    NOMBRES_CODIGO = [
        'codigo', 'código', 'code', 'item', 'itemcode', 'item code',
        'producto', 'sku', 'articulo', 'artículo', 'material'
    ]
    for nombre in NOMBRES_CODIGO:
        for idx, col in enumerate(columnas_originales):
            if nombre in col:
                resultado['codigo'] = df.columns[idx]
                break
        if 'codigo' in resultado:
            break
    
    # Si no encontró, usar la primera columna
    if 'codigo' not in resultado:
        resultado['codigo'] = df.columns[0]
    
    # Detectar columna de cantidad
    NOMBRES_CANTIDAD = [
        'cantidad', 'cant', 'qty', 'quantity', 'unidades', 'units',
        'solicitado', 'pedido', 'requested'
    ]
    for nombre in NOMBRES_CANTIDAD:
        for idx, col in enumerate(columnas_originales):
            if nombre in col:
                resultado['cantidad'] = df.columns[idx]
                break
        if 'cantidad' in resultado:
            break
    
    # Si no encontró cantidad, buscar columna numérica diferente a la primera
    if 'cantidad' not in resultado:
        for idx, col in enumerate(df.columns):
            if idx == 0:  # Saltar la primera (probablemente código)
                continue
            if pd.api.types.is_numeric_dtype(df[col]):
                resultado['cantidad'] = col
                break
    
    # Si aún no encontró, usar la última columna
    if 'cantidad' not in resultado:
        resultado['cantidad'] = df.columns[-1]
    
    # Detectar columna de descripción (opcional)
    NOMBRES_DESCRIPCION = [
        'descripcion', 'descripción', 'description', 'desc',
        'nombre', 'name', 'detalle', 'detail'
    ]
    for nombre in NOMBRES_DESCRIPCION:
        for idx, col in enumerate(columnas_originales):
            if nombre in col:
                resultado['descripcion'] = df.columns[idx]
                break
        if 'descripcion' in resultado:
            break
            
    # Detectar columna de bodega (opcional)
    NOMBRES_BODEGA = [
        'bodega', 'almacen', 'warehouse', 'ubicacion', 'location', 'deposito'
    ]
    for nombre in NOMBRES_BODEGA:
        for idx, col in enumerate(columnas_originales):
            if nombre in col:
                resultado['bodega'] = df.columns[idx]
                break
        if 'bodega' in resultado:
            break
    
    # Si hay 3+ columnas y no encontramos descripción, usar la del medio
    if 'descripcion' not in resultado and len(df.columns) >= 3:
        # Buscar columna que no sea código, cantidad ni bodega
        for col in df.columns:
            if col != resultado['codigo'] and col != resultado['cantidad'] and col != resultado.get('bodega'):
                resultado['descripcion'] = col
                break
    
    return resultado


def extraer_cantidad(valor: Any) -> int:
    """
    Extrae un número entero de cantidad desde diversos formatos.
    
    Maneja: int, float, string con números, etc.
    """
    try:
        # Convertir a float primero (por si viene como "10.0")
        cantidad_float = float(valor)
        # Luego a int
        cantidad = int(cantidad_float)
        
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a 0")
        
        return cantidad
        
    except (ValueError, TypeError):
        # Si no se puede convertir, retornar 1 por defecto
        return 1


def validar_excel_estructura(archivo_bytes: bytes) -> Dict[str, Any]:
    """
    Valida la estructura del Excel sin procesarlo completamente.
    Útil para dar feedback rápido al usuario.
    
    Returns:
        Dict con información del archivo: total_filas, columnas_detectadas, etc.
    """
    try:
        df = pd.read_excel(BytesIO(archivo_bytes))
        columnas = detectar_columnas(df)
        
        return {
            'valido': True,
            'total_filas': len(df),
            'columnas_detectadas': columnas,
            'nombres_columnas': list(df.columns)
        }
    except Exception as e:
        return {
            'valido': False,
            'error': str(e)
        }
