import pandas as pd
import os
from django.db import connection
from django.conf import settings
from supabase import create_client, Client
from .models import Stock, CargaStock

def get_supabase_client():
    """Retorna cliente de Supabase configurado"""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)

def procesar_archivo_stock(archivo, usuario):
    """
    Procesa un archivo Excel de stock:
    1. Sube a Supabase Storage
    2. Limpia stock antiguo
    3. Carga nuevo stock
    """
    # 1. Crear registro de carga
    carga = CargaStock.objects.create(
        usuario=usuario,
        nombre_archivo=archivo.name,
        estado='procesando'
    )
    
    try:
        # 2. Subir a Storage (si está configurado)
        supabase = get_supabase_client()
        if supabase:
            try:
                file_content = archivo.read()
                # Usar timestamp para evitar colisiones
                path = f"stock/{carga.id}_{archivo.name}"
                
                # Subir archivo
                supabase.storage.from_("stock-files").upload(
                    path=path,
                    file=file_content,
                    file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                )
                
                carga.archivo_url = path
                carga.save()
                
                # Resetear puntero para pandas
                archivo.seek(0)
            except Exception as e:
                print(f"⚠️ Error subiendo a Storage (continuando con carga): {e}")
                archivo.seek(0)
        
        # 3. Procesar con Pandas
        try:
            df = pd.read_excel(archivo)
        except Exception as e:
            raise ValueError(f"Error al leer Excel: {e}")
        
        # Validar columnas requeridas
        required_cols = ['Codigo', 'Descripcion', 'Cod.Bodega', 'Stock']
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
            
        # 4. Limpiar stock antiguo usando función SQL optimizada
        with connection.cursor() as cursor:
            cursor.execute("SELECT limpiar_stock_antiguo();")
            
        # 5. Preparar objetos para inserción masiva
        stock_objects = []
        errores_fila = 0
        
        for index, row in df.iterrows():
            try:
                # Validar datos mínimos
                codigo = str(row['Codigo']).strip()
                bodega = str(row['Cod.Bodega']).strip()
                
                if not codigo or not bodega:
                    continue
                    
                # Manejar valores numéricos
                stock_val = row['Stock']
                if pd.isna(stock_val): stock_val = 0
                
                precio_val = row.get('Precio $')
                if pd.isna(precio_val): precio_val = 0
                
                total_val = row.get('Total $')
                if pd.isna(total_val): total_val = 0
                
                stock_objects.append(Stock(
                    codigo=codigo,
                    descripcion=str(row['Descripcion'])[:255] if not pd.isna(row['Descripcion']) else '',
                    cod_grupo=int(row['Cod.Grupo']) if 'Cod.Grupo' in df.columns and not pd.isna(row['Cod.Grupo']) else None,
                    descripcion_grupo=str(row['Descripcion Grupo'])[:200] if 'Descripcion Grupo' in df.columns and not pd.isna(row['Descripcion Grupo']) else '',
                    bodega=bodega,
                    bodega_nombre=str(row['Descripcion Bodega'])[:200] if 'Descripcion Bodega' in df.columns and not pd.isna(row['Descripcion Bodega']) else '',
                    ubicacion=str(row['Ubicacion'])[:100] if 'Ubicacion' in df.columns and not pd.isna(row['Ubicacion']) else '',
                    ubicacion_2=str(row['Ubicacion 2'])[:100] if 'Ubicacion 2' in df.columns and not pd.isna(row['Ubicacion 2']) else '',
                    stock_disponible=int(stock_val),
                    stock_reservado=0,
                    precio=float(precio_val),
                    total=float(total_val),
                    categoria=str(row['Categoria'])[:100] if 'Categoria' in df.columns and not pd.isna(row['Categoria']) else ''
                ))
            except Exception as e:
                errores_fila += 1
                print(f"Error en fila {index}: {e}")
                continue
        
        # 6. Insertar en lotes (batch_size=1000)
        Stock.objects.bulk_create(stock_objects, batch_size=1000, ignore_conflicts=True)
        
        # 7. Actualizar estado de carga
        carga.total_productos = len(stock_objects)
        carga.total_bodegas = df['Cod.Bodega'].nunique()
        carga.estado = 'activo'
        carga.save()
        
        return {
            'success': True,
            'total_productos': carga.total_productos,
            'total_bodegas': carga.total_bodegas,
            'errores_fila': errores_fila
        }
        
    except Exception as e:
        carga.estado = 'error'
        carga.mensaje_error = str(e)
        carga.save()
        raise e
