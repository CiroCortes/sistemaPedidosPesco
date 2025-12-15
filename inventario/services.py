import pandas as pd
from django.db import transaction, connection
from django.utils import timezone
from .models import StockSAP, CargaStock
import time
import logging
from django.contrib.auth import get_user_model
from collections import defaultdict

logger = logging.getLogger(__name__)

class StockService:
    """
    Servicio para procesar y cargar archivos de stock SAP
    Adaptado a la estructura de tabla existente 'stock'
    """
    
    COLUMNAS_REQUERIDAS = [
        'Codigo', 'Descripcion', 'Cod.Bodega', 
        'Descripcion Bodega', 'Stock'
    ]
    
    def procesar_archivo(self, archivo, usuario):
        """
        Procesar archivo de stock y volcarlo a la base de datos
        """
        inicio = time.time()
        carga = None
        
        try:
            # 1. Crear registro de carga
            # Necesitamos un ID manual porque BigAutoField no siempre retorna el ID en managed=False si no está configurado
            # Pero intentemos dejar que la BD lo maneje si es serial
            
            usuario_id = usuario.id if usuario.is_authenticated else None
            
            carga = CargaStock(
                usuario_id=usuario_id,
                nombre_archivo=archivo.name,
                estado='procesando',
                fecha_carga=timezone.now()
            )
            carga.save()
            
            logger.info(f"Iniciando carga #{carga.id}")
            
            # 2. Leer archivo Excel
            df = pd.read_excel(archivo)
            total_filas = len(df)
            
            # 3. Validar columnas
            self._validar_columnas(df)
            
            # 4. Limpiar datos
            df = self._limpiar_datos(df)
            
            # 5. Crear objetos Stock
            stock_objects = self._crear_objetos_stock(df)
            
            # 6. Volcar a BD
            self._volcar_a_bd(stock_objects)
            
            # 7. Actualizar carga
            tiempo_proceso = time.time() - inicio
            
            # Contar bodegas únicas
            total_bodegas = df['Cod.Bodega'].nunique() if 'Cod.Bodega' in df.columns else 0
            
            carga.total_productos = total_filas
            carga.total_bodegas = total_bodegas
            carga.estado = 'completado'
            carga.save()
            
            return {
                'success': True,
                'registros': total_filas,
                'tiempo': tiempo_proceso,
                'mensaje': f'Se cargaron {total_filas:,} registros exitosamente'
            }
            
        except Exception as e:
            logger.error(f"Error en carga: {str(e)}", exc_info=True)
            if carga:
                carga.estado = 'error'
                carga.mensaje_error = str(e)
                carga.save()
            
            return {
                'success': False,
                'error': str(e),
                'mensaje': f'Error al procesar archivo: {str(e)}'
            }
    
    def _validar_columnas(self, df):
        columnas_faltantes = [col for col in self.COLUMNAS_REQUERIDAS if col not in df.columns]
        if columnas_faltantes:
            raise ValueError(f"Faltan columnas: {', '.join(columnas_faltantes)}")

    def _limpiar_datos(self, df):
        df = df.where(pd.notna(df), None)
        # Convertir Stock a numérico, default 0
        if 'Stock' in df.columns:
            df['Stock'] = pd.to_numeric(df['Stock'], errors='coerce').fillna(0)
        return df

    def _crear_objetos_stock(self, df):
        """
        Crea objetos Stock optimizado usando itertuples() en lugar de groupby().
        Agrupa por Codigo y Bodega, sumando stock y concatenando ubicaciones.
        """
        stock_objects = []
        
        # Diccionario para agrupar por (codigo, bodega) - más eficiente que groupby()
        grupos = defaultdict(lambda: {
            'stock_total': 0,
            'ubicaciones': set(),
            'primera_fila': None
        })
        
        # Crear mapeo de índices de columnas para acceso rápido
        col_indices = {col: list(df.columns).index(col) for col in df.columns}
        
        # Procesar todas las filas usando itertuples (más rápido que iterrows o groupby)
        for row in df.itertuples(index=False, name=None):
            try:
                # Acceder a columnas por índice (itertuples retorna tupla)
                codigo = str(row[col_indices['Codigo']]).strip() if col_indices.get('Codigo') is not None else ''
                bodega = str(row[col_indices['Cod.Bodega']]).strip() if col_indices.get('Cod.Bodega') is not None else ''
                
                if not codigo or not bodega:
                    continue
                
                clave = (codigo, bodega)
                
                # Obtener valores de la fila
                stock_val = 0
                if col_indices.get('Stock') is not None:
                    try:
                        stock_val = float(row[col_indices['Stock']]) if pd.notna(row[col_indices['Stock']]) else 0
                    except (ValueError, TypeError):
                        stock_val = 0
                
                # Guardar primera fila del grupo para datos generales
                if grupos[clave]['primera_fila'] is None:
                    grupos[clave]['primera_fila'] = row
                
                # Acumular stock
                grupos[clave]['stock_total'] += stock_val
                
                # Acumular ubicaciones únicas
                if col_indices.get('Ubicacion') is not None:
                    ubicacion = row[col_indices['Ubicacion']]
                    if pd.notna(ubicacion) and str(ubicacion).strip():
                        grupos[clave]['ubicaciones'].add(str(ubicacion).strip())
                        
            except Exception as e:
                logger.warning(f"Error procesando fila: {e}")
                continue
        
        # Crear objetos Stock a partir de los grupos
        ahora = timezone.now()
        for (codigo, bodega), datos in grupos.items():
            try:
                primera_fila = datos['primera_fila']
                
                # Obtener valores de la primera fila
                def get_val(col_name, default=None, max_len=None):
                    if col_indices.get(col_name) is None:
                        return default
                    val = primera_fila[col_indices[col_name]]
                    if pd.isna(val):
                        return default
                    val_str = str(val)
                    if max_len:
                        val_str = val_str[:max_len]
                    return val_str if default is None else val_str or default
                
                def get_num(col_name, default=0):
                    if col_indices.get(col_name) is None:
                        return default
                    val = primera_fila[col_indices[col_name]]
                    if pd.isna(val):
                        return default
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        return default
                
                # Concatenar ubicaciones
                ubicaciones = sorted(list(datos['ubicaciones']))
                ubicacion_str = ' / '.join(ubicaciones)[:100] if ubicaciones else None
                
                stock_obj = StockSAP(
                    codigo=codigo[:50],
                    descripcion=get_val('Descripcion', ''),
                    cod_grupo=int(get_num('Cod.Grupo')) if col_indices.get('Cod.Grupo') is not None and pd.notna(primera_fila[col_indices['Cod.Grupo']]) else None,
                    descripcion_grupo=get_val('Descripcion Grupo', '', 200),
                    bodega=bodega[:20],
                    bodega_nombre=get_val('Descripcion Bodega', '', 200),
                    ubicacion=ubicacion_str,
                    ubicacion_2=get_val('Ubicacion 2', None, 100),
                    stock_disponible=int(datos['stock_total']),
                    stock_reservado=0,
                    precio=get_num('Precio $'),
                    total=get_num('Total $'),
                    categoria=get_val('Categoria', None, 100),
                    ultima_actualizacion=ahora
                )
                stock_objects.append(stock_obj)
            except Exception as e:
                logger.warning(f"Error creando objeto Stock {codigo}-{bodega}: {e}")
                continue
                
        return stock_objects

    def _volcar_a_bd(self, stock_objects):
        """
        Volcar objetos Stock a BD usando TRUNCATE (mucho más rápido que DELETE)
        y bulk_create en lotes para mejor rendimiento.
        """
        with transaction.atomic():
            # TRUNCATE es mucho más rápido que DELETE para limpiar toda la tabla
            # No registra cada fila eliminada en el log de transacciones
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE stock RESTART IDENTITY CASCADE;")
                logger.info(f"Tabla stock truncada. Insertando {len(stock_objects)} registros...")
            
            # Insertar en lotes (batch_size=500 es un buen balance entre memoria y velocidad)
            batch_size = 500
            total_insertados = 0
            for i in range(0, len(stock_objects), batch_size):
                batch = stock_objects[i:i + batch_size]
                StockSAP.objects.bulk_create(batch, batch_size=batch_size, ignore_conflicts=False)
                total_insertados += len(batch)
                logger.info(f"Insertados {total_insertados}/{len(stock_objects)} registros...")
            
            logger.info(f"✅ Total de registros insertados: {total_insertados}")

    def obtener_stock_producto(self, codigo):
        return StockSAP.objects.filter(codigo=codigo)
