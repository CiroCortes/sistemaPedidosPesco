# Configuración de Supabase para Sistema PESCO

## 🎯 Problema Actual

Actualmente el sistema está configurado para usar PostgreSQL/Supabase, pero está cayendo en SQLite porque las variables de entorno no están configuradas correctamente en tu archivo `.env`.

## 📋 Pasos para Configurar Supabase

### 1. Obtener Credenciales de Supabase

Ve a tu proyecto en Supabase:
1. Abre tu proyecto en [https://supabase.com](https://supabase.com)
2. Ve a **Settings** (⚙️) → **Database**
3. Busca la sección **Connection String**
4. Copia la **Connection pooling** (Transaction mode o Session mode)

La URL se verá así:
```
postgres://postgres.[PROJECT_REF]:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

### 2. Editar tu archivo `.env`

Abre tu archivo `.env` (en la raíz del proyecto) y asegúrate de tener estas variables:

```env
# Django
SECRET_KEY=tu_secret_key_actual
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# SUPABASE DATABASE
DB_NAME=postgres
DB_USER=postgres.abcdefghijklmnop
DB_PASSWORD=tu_password_de_supabase
DB_HOST=aws-0-us-east-1.pooler.supabase.com
DB_PORT=6543

# GEMINI AI
GEMINI_API_KEY=tu_api_key_actual
GEMINI_MODEL=gemini-2.5-flash

# API TOKEN
IA_API_TOKEN=tu_token_actual
```

### 3. Desglosar la Connection String de Supabase

Si tu connection string es:
```
postgres://postgres.abcdefghijklmnop:mi_password_123@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

Entonces:
- `DB_USER` = `postgres.abcdefghijklmnop`
- `DB_PASSWORD` = `mi_password_123`
- `DB_HOST` = `aws-0-us-east-1.pooler.supabase.com`
- `DB_PORT` = `6543`
- `DB_NAME` = `postgres`

### 4. Verificar la Configuración

Después de editar el `.env`:

```powershell
# 1. Detén el servidor si está corriendo (CTRL+C)

# 2. Verifica que Django pueda conectarse a Supabase
python manage.py check --database default

# 3. Si todo está bien, verás:
# System check identified no issues (0 silenced).
```

### 5. Aplicar Migraciones a Supabase

```powershell
# Aplicar todas las migraciones
python manage.py migrate

# Deberías ver algo como:
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   Applying auth.0001_initial... OK
#   Applying core.0001_initial... OK
#   Applying solicitudes.0001_initial... OK
#   ... etc
```

### 6. Crear Superusuario (si es necesario)

```powershell
python manage.py createsuperuser
```

### 7. Iniciar el Servidor

```powershell
python manage.py runserver
```

## ✅ Verificar que Estás Usando Supabase

### Opción 1: Ver en el código
Agrega esto temporalmente en `solicitudes/views.py`:

```python
from django.db import connection

def lista_solicitudes(request):
    # Temporal: verificar qué BD estás usando
    print(f"Base de datos: {connection.settings_dict['ENGINE']}")
    print(f"Host: {connection.settings_dict['HOST']}")
    # ... resto del código
```

### Opción 2: Verificar en Supabase Dashboard
1. Ve a tu proyecto en Supabase
2. Ve a **Database** → **Tables**
3. Deberías ver las tablas:
   - `auth_user`
   - `core_usuario`
   - `solicitudes`
   - `solicitudes_detalle`
   - etc.

### Opción 3: Verificar índices
1. Ve a **Database** → **Indexes**
2. Deberías ver todos los índices que creamos:
   - `solicitudes_idx_estado`
   - `solicitudes_idx_estado_id`
   - `solicitudes_idx_cliente`
   - etc.

## 🔧 Solución de Problemas

### Error: "could not connect to server"
- Verifica que el `DB_HOST` sea correcto
- Verifica que el `DB_PORT` sea `6543` (pooler) o `5432` (directo)
- Verifica tu conexión a internet

### Error: "password authentication failed"
- Verifica que el `DB_PASSWORD` sea correcto
- Verifica que el `DB_USER` incluya el project ref: `postgres.abcdefghijklmnop`

### Error: "SSL connection required"
- Ya está configurado en `settings.py` con `'sslmode': 'require'`
- No necesitas hacer nada adicional

### Sigue usando SQLite
- Verifica que el archivo `.env` esté en la raíz del proyecto
- Verifica que las variables estén escritas correctamente (sin espacios extras)
- Reinicia el servidor después de editar `.env`

## 📊 Configuración Actual en settings.py

Tu `settings.py` ya está correctamente configurado:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'postgres'),
        'USER': os.getenv('DB_USER', 'postgres'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
        },
    }
}
```

El problema es que cuando las variables de entorno no existen, Django usa los valores por defecto:
- `HOST=localhost` → No encuentra PostgreSQL local → Cae en SQLite
- `PASSWORD=''` → Contraseña vacía → Falla la conexión

## 🎯 Resumen de Pasos

1. ✅ Abre tu archivo `.env`
2. ✅ Agrega/actualiza las variables de Supabase
3. ✅ Reinicia el servidor
4. ✅ Ejecuta `python manage.py migrate`
5. ✅ Verifica en Supabase Dashboard que las tablas e índices existen

## 📝 Ejemplo Completo de .env

```env
# Django
SECRET_KEY=django-insecure-ejemplo-no-usar-en-produccion
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Supabase
DB_NAME=postgres
DB_USER=postgres.abcdefghijklmnop
DB_PASSWORD=mi_password_super_secreto_123
DB_HOST=aws-0-us-east-1.pooler.supabase.com
DB_PORT=6543

# Gemini
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-2.5-flash

# API
IA_API_TOKEN=token_secreto_para_api_ia_minimo_32_caracteres_aleatorios
```

---

**Última actualización**: Noviembre 2024

