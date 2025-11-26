"""
Script para verificar y resetear el usuario admin
"""
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

django.setup()

from core.models import Usuario

print("=" * 60)
print("VERIFICACIÓN Y RESET DE USUARIO ADMIN")
print("=" * 60)

# Verificar usuarios existentes
print("\n1. Usuarios en la base de datos:")
usuarios = Usuario.objects.all()
print(f"   Total: {usuarios.count()}")

for user in usuarios:
    print(f"   - {user.username} | {user.email} | Rol: {user.rol} | Activo: {user.is_active} | Superuser: {user.is_superuser}")

# Verificar/crear admin
print("\n2. Verificando usuario 'admin'...")

try:
    admin = Usuario.objects.get(username='admin')
    print(f"   ✓ Usuario 'admin' existe")
    print(f"   Email: {admin.email}")
    print(f"   Rol: {admin.rol}")
    print(f"   Activo: {admin.is_active}")
    print(f"   Superuser: {admin.is_superuser}")
    
    # Resetear contraseña
    print("\n3. Reseteando contraseña...")
    admin.set_password('admin123')
    admin.is_active = True
    admin.is_superuser = True
    admin.is_staff = True
    admin.rol = 'admin'
    admin.save()
    print("   ✓ Contraseña reseteada a: admin123")
    print("   ✓ Usuario configurado como superusuario activo")
    
except Usuario.DoesNotExist:
    print("   ⚠️  Usuario 'admin' NO existe, creando...")
    admin = Usuario.objects.create_superuser(
        username='admin',
        email='admin@pesco.cl',
        password='admin123',
        nombre_completo='Administrador Principal',
        rol='admin'
    )
    print("   ✓ Usuario 'admin' creado")
    print("   Email: admin@pesco.cl")
    print("   Password: admin123")

print("\n" + "=" * 60)
print("✅ VERIFICACIÓN COMPLETADA")
print("=" * 60)
print("\nCredenciales de login:")
print("  Usuario: admin")
print("  Password: admin123")
print("\nPrueba el login en: http://localhost:8000/login/")
print("=" * 60)
