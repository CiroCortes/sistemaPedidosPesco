import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("VERIFICACIÓN DE CREDENCIALES EN .ENV")
print("=" * 80)

db_user = os.getenv('DB_USER', '')
db_host = os.getenv('DB_HOST', '')
db_port = os.getenv('DB_PORT', '')
db_name = os.getenv('DB_NAME', '')

print(f"\nDB_USER: {db_user}")
print(f"Longitud: {len(db_user)} caracteres")
print(f"\nDB_HOST: {db_host}")
print(f"\nDB_PORT: {db_port}")
print(f"\nDB_NAME: {db_name}")

print("\n" + "=" * 80)
print("CADENA DE CONEXIÓN ESPERADA (según Supabase):")
print("=" * 80)
print("postgresql://postgres.wslufnwvuleboghybtjz:[PASSWORD]@aws-1-us-east-2.pooler.supabase.com:5432/postgres")

print("\n" + "=" * 80)
print("CADENA DE CONEXIÓN ACTUAL (según tu .env):")
print("=" * 80)
print(f"postgresql://{db_user}:[PASSWORD]@{db_host}:{db_port}/{db_name}")

print("\n" + "=" * 80)
print("COMPARACIÓN:")
print("=" * 80)
expected_user = "postgres.wslufnwvuleboghybtjz"
if db_user == expected_user:
    print("✅ Usuario CORRECTO")
else:
    print(f"❌ Usuario INCORRECTO")
    print(f"   Esperado: {expected_user}")
    print(f"   Actual:   {db_user}")
    print(f"\n   Diferencias:")
    for i, (c1, c2) in enumerate(zip(expected_user, db_user)):
        if c1 != c2:
            print(f"   Posición {i}: esperado '{c1}', actual '{c2}'")
