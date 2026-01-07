# 🚀 Guía de Despliegue a Producción - Sistema PESCO

## 📋 Checklist Pre-Despliegue

### ✅ Configuración Actual del Sistema

El sistema ya está **preparado para producción** con las siguientes características:

- ✅ `DEBUG` configurable desde variable de entorno
- ✅ `SECRET_KEY` desde variable de entorno (no hardcodeado)
- ✅ `ALLOWED_HOSTS` configurable desde variable de entorno
- ✅ Base de datos PostgreSQL (Supabase) con `DATABASE_URL`
- ✅ WhiteNoise para servir archivos estáticos
- ✅ Configuraciones de seguridad HTTPS automáticas cuando `DEBUG=False`
- ✅ Zona horaria configurada a `America/Santiago` (Chile)
- ✅ Idioma configurado a `es-cl` (Español Chile)

---

## 🔐 Variables de Entorno para Producción

### Variables OBLIGATORIAS en Render.com:

```bash
# 1. DEBUG - Por defecto es False (producción)
# Solo configurar si quieres activar modo debug (NO recomendado en producción)
# DEBUG=False  # Ya es el valor por defecto, no es necesario configurarlo

# 2. SECRET_KEY - Generar una nueva clave segura
# Para generar una nueva clave, ejecutar localmente:
# python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY=tu-nueva-clave-super-segura-generada

# 3. ALLOWED_HOSTS - Dominio de tu aplicación
# Ejemplo para Render: sistema-pesco.onrender.com
# Si tienes dominio personalizado: www.tupesco.com,tupesco.com
ALLOWED_HOSTS=sistema-pesco.onrender.com

# 4. DATABASE_URL - Render lo proporciona automáticamente
# Si usas PostgreSQL de Render, se configura automáticamente
# Si usas Supabase externo, copiarlo del dashboard de Supabase
DATABASE_URL=postgresql://usuario:password@host.supabase.co:5432/postgres
```

### Variables OPCIONALES:

```bash
# Token para API de IA (solo si usas integraciones externas)
IA_API_TOKEN=tu-token-opcional
```

---

## 📦 Pasos para Desplegar en Render.com

### 1. Preparar el Repositorio Git

```bash
# Asegurarte de que .env está en .gitignore
echo ".env" >> .gitignore

# Commitear todos los cambios
git add .
git commit -m "Preparar sistema para producción"
git push origin main
```

### 2. Crear Servicio Web en Render

1. Ir a [render.com](https://render.com) y crear cuenta
2. Click en **"New +"** → **"Web Service"**
3. Conectar tu repositorio GitHub/GitLab
4. Configurar el servicio:

**Build Settings:**
- **Build Command:**
  ```bash
  pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate
  ```

- **Start Command:**
  ```bash
  gunicorn backend.wsgi:application
  ```

**Environment:**
- **Python Version:** 3.11 o superior

### 3. Configurar Variables de Entorno

En el dashboard de Render, ir a **"Environment"** y agregar:

```
DEBUG=False
SECRET_KEY=<generar-nueva-clave-segura>
ALLOWED_HOSTS=tu-app.onrender.com
DATABASE_URL=<tu-database-url>
```

### 4. Crear Base de Datos PostgreSQL (si no tienes Supabase)

**Opción A: PostgreSQL en Render**
1. Click en **"New +"** → **"PostgreSQL"**
2. Crear base de datos
3. Copiar el **"External Database URL"**
4. Pegarlo en la variable `DATABASE_URL` del Web Service

**Opción B: Usar Supabase existente**
1. Ir a dashboard de Supabase
2. Settings → Database → Connection string (URI)
3. Copiar el connection string
4. Pegarlo en la variable `DATABASE_URL`

### 5. Desplegar

1. Click en **"Manual Deploy"** → **"Deploy latest commit"**
2. Esperar a que termine el build (3-5 minutos)
3. Verificar que no haya errores en los logs

---

## 🔍 Verificación Post-Despliegue

### 1. Verificar que el sitio cargue
- Abrir `https://tu-app.onrender.com`
- Debe mostrar la página de login

### 2. Verificar archivos estáticos
- CSS y JavaScript deben cargar correctamente
- Verificar en DevTools (F12) que no haya errores 404

### 3. Crear superusuario (si es primera vez)

Desde el dashboard de Render, ir a **"Shell"** y ejecutar:
```bash
python manage.py createsuperuser
```

### 4. Verificar funcionalidades críticas
- ✅ Login funciona
- ✅ Dashboard carga correctamente
- ✅ Módulo de solicitudes funciona
- ✅ Módulo de bodega funciona
- ✅ Módulo de despacho funciona
- ✅ Reportes se generan correctamente
- ✅ Fechas muestran hora de Chile

---

## 🔧 Configuraciones de Seguridad Activadas

Cuando `DEBUG=False`, el sistema activa automáticamente:

✅ **HTTPS Obligatorio:**
- `SECURE_SSL_REDIRECT = True`
- Todas las peticiones HTTP redirigen a HTTPS

✅ **Cookies Seguras:**
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- Cookies solo se envían por HTTPS

✅ **HSTS (HTTP Strict Transport Security):**
- `SECURE_HSTS_SECONDS = 31536000` (1 año)
- Los navegadores recordarán usar HTTPS siempre

✅ **Headers de Seguridad:**
- `X_FRAME_OPTIONS = 'DENY'` (previene clickjacking)
- `SECURE_CONTENT_TYPE_NOSNIFF = True`
- `SECURE_BROWSER_XSS_FILTER = True`

---

## 📊 Monitoreo y Logs

### Ver logs en tiempo real (Render):
1. Ir al dashboard del servicio
2. Click en **"Logs"**
3. Monitorear errores o warnings

### Limpiar cache si hay problemas:
```bash
# Desde el Shell de Render
python manage.py shell -c "from django.core.cache import cache; cache.clear()"
```

---

## 🆘 Solución de Problemas Comunes

### Error: "DisallowedHost at /"
**Causa:** El dominio no está en `ALLOWED_HOSTS`
**Solución:** Agregar el dominio a la variable de entorno `ALLOWED_HOSTS`

### Error: "500 Internal Server Error"
**Causa:** Variable de entorno faltante o error en el código
**Solución:** Revisar los logs en Render para ver el error específico

### Error: Archivos estáticos no cargan (404)
**Causa:** `collectstatic` no se ejecutó
**Solución:** Verificar que el Build Command incluya `python manage.py collectstatic --noinput`

### Error: Base de datos no conecta
**Causa:** `DATABASE_URL` incorrecto o base de datos no accesible
**Solución:** Verificar que la URL sea correcta y que la base de datos esté activa

### Fechas incorrectas
**Causa:** Zona horaria no configurada
**Solución:** Verificar que `TIME_ZONE = 'America/Santiago'` y `USE_TZ = True`

---

## 🔄 Actualizaciones Futuras

Para actualizar el sistema en producción:

1. **Hacer cambios localmente y probar**
2. **Commitear y pushear a GitHub:**
   ```bash
   git add .
   git commit -m "Descripción del cambio"
   git push origin main
   ```
3. **Desplegar en Render:**
   - Render detecta automáticamente el push y redespliega
   - O hacer deploy manual desde el dashboard

---

## 📝 Comandos Útiles

### Generar nueva SECRET_KEY:
```bash
python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Ejecutar migraciones en producción:
```bash
python manage.py migrate
```

### Crear usuarios de prueba en producción:
```bash
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.create_user(username='bodega', password='bodega123', rol='bodega', bodegas_asignadas='013-02,013-03')
```

### Limpiar cache:
```bash
python manage.py shell -c "from django.core.cache import cache; cache.clear(); print('Cache limpiado')"
```

---

## ✅ Sistema Listo para Producción

El sistema **Sistema PESCO** está completamente preparado para despliegue en producción con:

- 🔒 Configuraciones de seguridad robustas
- 🌐 Soporte para HTTPS automático
- 📊 Base de datos PostgreSQL configurada
- 🎨 Archivos estáticos optimizados con WhiteNoise
- 🕐 Zona horaria de Chile configurada
- 🔐 Variables de entorno para configuración flexible
- 👥 Sistema de roles y permisos implementado
- 📈 Dashboard con métricas en tiempo real
- 🤖 Integración con IA (Gemini)

---

**Última actualización:** Enero 2026
**Versión:** 1.0 - Producción Ready

