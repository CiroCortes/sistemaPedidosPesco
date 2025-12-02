import pandas as pd
from django.db import transaction
from django.utils import timezone
from .models import StockSAP, CargaStock
import time
import logging
from django.contrib.auth import get_user_model

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
        stock_objects = []
        
        # Agrupar por Codigo y Bodega para evitar duplicados (constraint unique)
        # Sumamos el stock y concatenamos ubicaciones si hay múltiples
        grupos = df.groupby(['Codigo', 'Cod.Bodega'])
        
        for (codigo, bodega), grupo in grupos:
            try:
                # Tomamos la primera fila del grupo para los datos generales
                row = grupo.iloc[0]
                
                # Sumamos el stock total del grupo
                stock_total = grupo['Stock'].sum()
                
                # Concatenamos ubicaciones si son distintas
                ubicaciones = grupo['Ubicacion'].dropna().unique()
                ubicacion_str = ' / '.join(map(str, ubicaciones))[:100] if len(ubicaciones) > 0 else None
                
                stock_obj = StockSAP(
                    codigo=str(codigo)[:50],
                    descripcion=row.get('Descripcion', ''),
                    cod_grupo=row.get('Cod.Grupo'),
                    descripcion_grupo=str(row.get('Descripcion Grupo', ''))[:200],
                    bodega=str(bodega)[:20],
                    bodega_nombre=str(row.get('Descripcion Bodega', ''))[:200],
                    ubicacion=ubicacion_str,
                    ubicacion_2=str(row.get('Ubicacion 2', ''))[:100] if row.get('Ubicacion 2') else None,
                    
                    # Stock sumado convertido a entero
                    stock_disponible=int(float(stock_total)),
                    stock_reservado=0,
                    
                    precio=row.get('Precio $'),
                    total=row.get('Total $'),
                    categoria=str(row.get('Categoria', ''))[:100] if row.get('Categoria') else None,
                    
                    ultima_actualizacion=timezone.now()
                )
                stock_objects.append(stock_obj)
            except Exception as e:
                logger.warning(f"Error procesando grupo {codigo}-{bodega}: {e}")
                continue
                
        return stock_objects

    def _volcar_a_bd(self, stock_objects):
        with transaction.atomic():
            # Borrar todo
            StockSAP.objects.all().delete()
            
            # Insertar en lotes
            batch_size = 500
            StockSAP.objects.bulk_create(stock_objects, batch_size=batch_size)

    def obtener_stock_producto(self, codigo):
        return StockSAP.objects.filter(codigo=codigo)
