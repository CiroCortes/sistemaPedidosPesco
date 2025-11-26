"""
Script para verificar la conexión a Supabase
"""
import os
from dotenv import load_dotenv
import psycopg2

# Cargar variables de entorno
load_dotenv()

print("=" * 80)
print("VERIFICACIÓN DE CONEXIÓN A SUPABASE")
print("=" * 80)

# Mostrar configuración (sin mostrar password)
print("\nConfiguración detectada:")
print(f"  Host: {os.getenv('DB_HOST')}")
print(f"  Port: {os.getenv('DB_PORT')}")
print(f"  Database: {os.getenv('DB_NAME')}")
print(f"  User: {os.getenv('DB_USER')}")
print(f"  Password: {'*' * len(os.getenv('DB_PASSWORD', ''))}")

print("\nIntentando conectar...")

try:
    # Intentar conexión
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT')
    )
    
    print("✅ ¡Conexión exitosa a Supabase!")
    
    # Verificar tablas existentes
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    
    print(f"\n📊 Tablas encontradas en la base de datos: {len(tables)}")
    if tables:
        for table in tables:
            print(f"  ✓ {table[0]}")
    else:
        print("  ⚠️ No hay tablas creadas aún. Necesitas ejecutar el script SQL.")
    
    # Cerrar conexión
    cur.close()
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ VERIFICACIÓN COMPLETADA EXITOSAMENTE")
    print("=" * 80)
    
except psycopg2.OperationalError as e:
    print(f"\n❌ Error de conexión:")
    print(f"   {e}")
    print("\n💡 Posibles causas:")
    print("   1. Password incorrecta")
    print("   2. Host incorrecto")
    print("   3. Firewall bloqueando la conexión")
    print("   4. Proyecto de Supabase pausado")
    
except Exception as e:
    print(f"\n❌ Error inesperado: {e}")
    import traceback
    traceback.print_exc()
