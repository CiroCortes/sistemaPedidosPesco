import os
from pathlib import Path
from dotenv import load_dotenv
import django

# Forzar carga de .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.conf import settings
from core.models import Usuario

def reset_password():
    print("="*80)
    print("DIAGNÓSTICO DE CONEXIÓN")
    print("="*80)
    print(f"USE_SUPABASE (env): {os.getenv('USE_SUPABASE')}")
    print(f"DB ENGINE: {settings.DATABASES['default']['ENGINE']}")
    print(f"DB HOST: {settings.DATABASES['default'].get('HOST', 'N/A')}")
    
    username = 'admin'
    new_pass = 'simple1234'
    
    print("\n" + "="*80)
    print(f"RESETEANDO PASSWORD PARA: {username}")
    print("="*80)
    
    try:
        user = Usuario.objects.get(username=username)
        print(f"✅ Usuario encontrado (ID: {user.id})")
        print(f"   Email: {user.email}")
        print(f"   Activo: {user.is_active}")
        
        print(f"Cambiar password a '{new_pass}'...")
        user.set_password(new_pass)
        user.save()
        print("✅ Password actualizada correctamente.")
        
    except Usuario.DoesNotExist:
        print(f"❌ El usuario '{username}' NO existe en la base de datos.")
        print("Creando usuario admin...")
        Usuario.objects.create_superuser(username, 'admin@example.com', new_pass)
        print("✅ Usuario admin creado con password 'simple1234'.")

if __name__ == '__main__':
    reset_password()
