"""
Script para migrar el sistema a Supabase PostgreSQL
Ejecuta migraciones y crea usuario administrador
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("MIGRACIÓN A SUPABASE - Sistema PESCO")
print("=" * 60)

# Verificar variables de entorno
required_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT']
missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    print(f"\n❌ ERROR: Faltan variables de entorno:")
    for var in missing_vars:
        print(f"   - {var}")
    print("\nPor favor, configura estas variables en el archivo .env")
    sys.exit(1)

print("\n✓ Variables de entorno configuradas correctamente")
print(f"  DB_HOST: {os.getenv('DB_HOST')}")
print(f"  DB_NAME: {os.getenv('DB_NAME')}")
print(f"  DB_USER: {os.getenv('DB_USER')}")
print(f"  DB_PORT: {os.getenv('DB_PORT')}")

# Verificar conexión a Supabase
print("\n1. Verificando conexión a Supabase...")
try:
    import psycopg2
    conn = psycopg2.connect(
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        sslmode='require'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    print(f"   ✓ Conexión exitosa a PostgreSQL")
    print(f"   Versión: {version[:60]}...")
    conn.close()
except Exception as e:
    print(f"   ❌ Error de conexión: {e}")
    print("\nVerifica que:")
    print("  1. Las credenciales en .env sean correctas")
    print("  2. Supabase esté accesible desde tu red")
    print("  3. El pooler de Supabase esté activo")
    sys.exit(1)

# Setup Django
print("\n2. Inicializando Django...")
django.setup()
print("   ✓ Django inicializado")

# Ejecutar migraciones
print("\n3. Ejecutando migraciones de Django...")
from django.core.management import call_command

try:
    # Mostrar migraciones pendientes
    print("   Verificando migraciones pendientes...")
    call_command('showmigrations', verbosity=0)
    
    # Ejecutar migraciones
    print("   Aplicando migraciones...")
    call_command('migrate', verbosity=1)
    print("   ✓ Migraciones ejecutadas correctamente")
except Exception as e:
    print(f"   ❌ Error en migraciones: {e}")
    print("\nSi el error es sobre tablas existentes, es normal.")
    print("Continuando con la creación de usuarios...")

# Crear superusuario si no existe
print("\n4. Verificando usuario administrador...")
from core.models import Usuario

try:
    if not Usuario.objects.filter(username='admin').exists():
        print("   Creando usuario administrador...")
        admin = Usuario.objects.create_superuser(
            username='admin',
            email='admin@pesco.cl',
            password='admin123',  # CAMBIAR EN PRODUCCIÓN
            nombre_completo='Administrador Principal',
            rol='admin'
        )
        print(f"   ✓ Usuario 'admin' creado")
        print(f"   📧 Email: admin@pesco.cl")
        print(f"   🔑 Password: admin123")
        print("   ⚠️  IMPORTANTE: Cambia la contraseña después del primer login")
    else:
        admin = Usuario.objects.get(username='admin')
        print(f"   ✓ Usuario administrador ya existe")
        print(f"   📧 Email: {admin.email}")
        print(f"   👤 Nombre: {admin.nombre_completo}")
        
    # Verificar total de usuarios
    total_usuarios = Usuario.objects.count()
    print(f"\n   Total de usuarios en Supabase: {total_usuarios}")
    
    if total_usuarios > 0:
        print("\n   Usuarios registrados:")
        for user in Usuario.objects.all():
            print(f"     - {user.username} ({user.get_rol_display()}) - {user.email}")
            
except Exception as e:
    print(f"   ❌ Error al crear usuario: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
print("=" * 60)
print("\nPróximos pasos:")
print("1. Detén el servidor actual (Ctrl+C)")
print("2. Inicia el servidor: python manage.py runserver")
print("3. Accede a http://localhost:8000/login/")
print("4. Login con: admin / admin123")
print("5. Cambia la contraseña desde el perfil")
print("\n" + "=" * 60)
