# 🚀 Despliegue en Render.com

## Pasos Rápidos

1. **Dashboard → New + → Web Service**
2. Conecta tu repositorio Git
3. Configura:
   - **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start Command**: `gunicorn backend.wsgi:application`
4. Copia las variables de entorno de tu `.env` local (solo cambia `DEBUG=False` y `ALLOWED_HOSTS=tu-app.onrender.com`)
5. **Create Web Service**

## Después del despliegue

En la Shell de Render:
```bash
python manage.py migrate
python manage.py createsuperuser  # Si no existe
```

¡Listo!
