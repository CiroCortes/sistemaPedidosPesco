import os
import psycopg2
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

def setup_database():
    print("="*80)
    print("CONFIGURANDO BASE DE DATOS SUPABASE")
    print("="*80)
    
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            port=os.getenv('DB_PORT'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database=os.getenv('DB_NAME'),
            sslmode='require'
        )
        cur = conn.cursor()
        
        # SQL Script
        sql_commands = [
            """
            CREATE TABLE IF NOT EXISTS stock (
                id BIGSERIAL PRIMARY KEY,
                codigo VARCHAR(50) NOT NULL,
                descripcion TEXT,
                cod_grupo INTEGER,
                descripcion_grupo VARCHAR(200),
                bodega VARCHAR(20) NOT NULL,
                bodega_nombre VARCHAR(200),
                ubicacion VARCHAR(100),
                ubicacion_2 VARCHAR(100),
                stock_disponible INTEGER NOT NULL DEFAULT 0,
                stock_reservado INTEGER NOT NULL DEFAULT 0,
                precio DECIMAL(12,3),
                total DECIMAL(15,3),
                categoria VARCHAR(100),
                ultima_actualizacion TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(codigo, bodega)
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_stock_codigo ON stock(codigo);",
            "CREATE INDEX IF NOT EXISTS idx_stock_bodega ON stock(bodega);",
            "CREATE INDEX IF NOT EXISTS idx_stock_codigo_bodega ON stock(codigo, bodega);",
            "CREATE INDEX IF NOT EXISTS idx_stock_disponible ON stock(stock_disponible) WHERE stock_disponible > 0;",
            
            """
            CREATE TABLE IF NOT EXISTS carga_stock (
                id BIGSERIAL PRIMARY KEY,
                fecha_carga TIMESTAMP DEFAULT NOW(),
                usuario_id INTEGER,
                nombre_archivo VARCHAR(255),
                total_productos INTEGER,
                total_bodegas INTEGER,
                archivo_url TEXT,
                estado VARCHAR(20) DEFAULT 'procesando',
                mensaje_error TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """,
            
            """
            CREATE OR REPLACE FUNCTION limpiar_stock_antiguo()
            RETURNS void AS $$
            BEGIN
                UPDATE carga_stock SET estado = 'expirado' WHERE estado = 'activo';
                DELETE FROM stock;
            END;
            $$ LANGUAGE plpgsql;
            """,
            
            """
            CREATE OR REPLACE VIEW stock_disponible AS
            SELECT 
                id, codigo, descripcion, bodega, bodega_nombre, ubicacion,
                stock_disponible, stock_reservado,
                (stock_disponible - stock_reservado) AS stock_real,
                CASE 
                    WHEN (stock_disponible - stock_reservado) <= 0 THEN 'sin_stock'
                    WHEN (stock_disponible - stock_reservado) <= 5 THEN 'stock_bajo'
                    ELSE 'disponible'
                END AS estado_stock,
                ultima_actualizacion
            FROM stock
            WHERE stock_disponible > 0
            ORDER BY codigo, bodega;
            """
        ]
        
        for command in sql_commands:
            print(f"Ejecutando: {command[:50]}...")
            cur.execute(command)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tablas e índices creados correctamente.")
        
    except Exception as e:
        print(f"❌ Error en BD: {e}")

def setup_storage():
    print("\n" + "="*80)
    print("CONFIGURANDO SUPABASE STORAGE")
    print("="*80)
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("❌ Faltan credenciales SUPABASE_URL o SUPABASE_KEY")
        return

    try:
        supabase: Client = create_client(url, key)
        bucket_name = "stock-files"
        
        # Listar buckets para ver si existe
        buckets = supabase.storage.list_buckets()
        exists = any(b.name == bucket_name for b in buckets)
        
        if not exists:
            print(f"Creando bucket '{bucket_name}'...")
            supabase.storage.create_bucket(bucket_name, options={"public": False})
            print(f"✅ Bucket '{bucket_name}' creado.")
        else:
            print(f"✅ Bucket '{bucket_name}' ya existe.")
            
    except Exception as e:
        print(f"❌ Error en Storage: {e}")

if __name__ == "__main__":
    setup_database()
    setup_storage()
