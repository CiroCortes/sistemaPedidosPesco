"""
Script para crear usuarios de prueba en Supabase
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
print("CREACIÓN DE USUARIOS DE PRUEBA")
print("=" * 60)

usuarios_prueba = [
    {
        'username': 'admin',
        'email': 'admin@pesco.cl',
        'password': 'admin123',
        'nombre_completo': 'Administrador Principal',
        'rol': 'admin',
        'is_superuser': True,
        'is_staff': True
    },
    {
        'username': 'bodega1',
        'email': 'bodega@pesco.cl',
        'password': 'bodega123',
        'nombre_completo': 'Usuario Bodega',
        'rol': 'bodega',
        'is_superuser': False,
        'is_staff': False
    },
    {
        'username': 'despacho1',
        'email': 'despacho@pesco.cl',
        'password': 'despacho123',
        'nombre_completo': 'Usuario Despacho',
        'rol': 'despacho',
        'is_superuser': False,
        'is_staff': False
    }
]

created_count = 0
existing_count = 0

for user_data in usuarios_prueba:
    username = user_data['username']
    
    if Usuario.objects.filter(username=username).exists():
        print(f"⚠️  Usuario '{username}' ya existe, saltando...")
        existing_count += 1
        continue
    
    password = user_data.pop('password')
    user = Usuario.objects.create_user(**user_data)
    user.set_password(password)
    user.save()
    
    print(f"✓ Usuario '{username}' creado (password: {password})")
    created_count += 1

print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print(f"Usuarios creados: {created_count}")
print(f"Usuarios existentes: {existing_count}")
print(f"Total en base de datos: {Usuario.objects.count()}")

print("\n" + "=" * 60)
print("CREDENCIALES DE ACCESO")
print("=" * 60)
print("\n🔐 Usuarios disponibles:")
print("  - admin / admin123 (Administrador)")
print("  - bodega1 / bodega123 (Bodega)")
print("  - despacho1 / despacho123 (Despacho)")
print("\n⚠️  Cambia las contraseñas en producción")
print("=" * 60)
