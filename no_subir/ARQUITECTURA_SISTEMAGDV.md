# 🏗️ Arquitectura Basada en sistemaGDV para PESCO

## 📚 Referencia
**Repositorio base**: [https://github.com/CiroCortes/sistemaGDV](https://github.com/CiroCortes/sistemaGDV)

---

## 🎯 Estructura del Proyecto PESCO (Basada en GDV)

```
sistemaPesco/
│
├── backend/                      # ⭐ Configuración Django (como GDV)
│   ├── __init__.py
│   ├── settings.py              # Configuración principal
│   ├── urls.py                  # URLs principales
│   ├── wsgi.py                  # WSGI para deployment
│   └── asgi.py                  # ASGI (futuro WebSockets)
│
├── core/                         # ⭐ Funcionalidades centrales (como GDV)
│   ├── models.py                # Modelo Usuario con roles
│   ├── views.py                 # Dashboard principal
│   ├── decorators.py            # @role_required, @admin_only
│   ├── middleware.py            # Middleware personalizado
│   └── templatetags/            # Template filters personalizados
│
├── frontend_django/              # ⭐ Templates y vistas (como GDV)
│   ├── templates/
│   │   ├── base.html           # Template base con navbar
│   │   ├── dashboard.html      # Dashboard principal
│   │   ├── login.html          # Página de login
│   │   └── components/         # Componentes reutilizables
│   │       ├── navbar.html
│   │       ├── sidebar.html
│   │       ├── card_kpi.html
│   │       └── table.html
│   │
│   └── static/
│       ├── css/
│       │   ├── bootstrap.min.css
│       │   └── custom.css      # Estilos personalizados PESCO
│       ├── js/
│       │   ├── bootstrap.bundle.min.js
│       │   ├── chart.min.js
│       │   └── app.js          # JavaScript principal
│       └── img/
│           └── logo_pesco.png
│
├── solicitudes/                  # App de Solicitudes (similar a productos/ en GDV)
│   ├── models.py                # Modelo Solicitud
│   ├── views.py                 # Vistas CRUD
│   ├── forms.py                 # Formularios Django
│   ├── urls.py                  # URLs de la app
│   ├── admin.py                 # Admin de Django
│   └── templates/solicitudes/
│       ├── lista.html
│       ├── crear.html
│       └── detalle.html
│
├── bodega/                       # App de Bodega (similar a almacenes/ en GDV)
│   ├── models.py                # Modelo Transferencia
│   ├── views.py                 # Vistas solo para usuario bodega
│   ├── forms.py                 # Form de transferencia
│   ├── urls.py
│   └── templates/bodega/
│       ├── panel.html           # Panel principal de bodega
│       └── transferencia_form.html
│
├── despacho/                     # App de Despacho (similar a entregas/ en GDV)
│   ├── models.py                # Modelo Embalaje
│   ├── views.py                 # Vistas solo para usuario despacho
│   ├── forms.py                 # Form de embalaje
│   ├── etiquetas.py             # Generación de etiquetas PDF
│   ├── urls.py
│   └── templates/despacho/
│       ├── panel.html
│       ├── embalaje_form.html
│       └── etiqueta_pdf.html
│
├── guias/                        # App de Guías SAP (NUEVO - solo para PESCO)
│   ├── models.py                # Registro de guías
│   ├── views.py                 # Vistas solo para admin
│   ├── forms.py                 # Form guía + OT
│   ├── urls.py
│   └── templates/guias/
│       └── panel_admin.html
│
├── reportes/                     # App de Reportes (nuevo)
│   ├── views.py                 # Vistas de reportes
│   ├── exporters.py             # Exportación a Excel
│   ├── kpis.py                  # Cálculo de KPIs
│   ├── urls.py
│   └── templates/reportes/
│       ├── dashboard_kpis.html
│       └── exportar.html
│
├── api/                          # API REST (opcional, como GDV)
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── requirements.txt              # ⭐ Dependencias (basado en GDV)
├── runtime.txt                   # ⭐ Python 3.11
├── build.sh                      # ⭐ Script para Render
├── env_ejemplo.txt               # ⭐ Plantilla de .env
├── .gitignore                    # ⭐ Archivos a ignorar
├── manage.py                     # ⭐ Script Django
└── README.MD                     # Documentación principal
```

---

## 🎨 Paleta de Colores PESCO (Aplicar sobre GDV)

### Colores Principales
```css
/* custom.css - Sobrescribir Bootstrap */

:root {
    --pesco-primary: #00B4D8;      /* Azul turquesa - Principal */
    --pesco-success: #4CAF50;      /* Verde - Completado */
    --pesco-warning: #FFC107;      /* Amarillo - Pendiente */
    --pesco-danger: #F44336;       /* Rojo - Cancelado/Crítico */
    --pesco-secondary: #6C757D;    /* Gris - Secundario */
    --pesco-light: #F8F9FA;        /* Fondo claro */
    --pesco-dark: #212529;         /* Texto oscuro */
}

/* Sobrescribir botones de Bootstrap */
.btn-primary {
    background-color: var(--pesco-primary);
    border-color: var(--pesco-primary);
}

.btn-primary:hover {
    background-color: #0096B8;
}

/* Navbar */
.navbar {
    background-color: var(--pesco-primary) !important;
}

/* Cards de KPIs */
.card-kpi {
    border-left: 4px solid var(--pesco-primary);
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    transition: transform 0.2s;
}

.card-kpi:hover {
    transform: translateY(-5px);
}

/* Estados con colores */
.badge-pendiente {
    background-color: var(--pesco-warning);
}

.badge-en-despacho {
    background-color: var(--pesco-primary);
}

.badge-embalado {
    background-color: #8BC34A; /* Verde claro */
}

.badge-despachado {
    background-color: var(--pesco-success);
}

.badge-cancelado {
    background-color: var(--pesco-danger);
}
```

---

## 📦 Requirements.txt (Basado en GDV + PESCO)

```txt
# Core Django
Django==5.2.6
python-dotenv==1.0.0

# Base de datos
psycopg2-binary==2.9.9
supabase==2.3.0

# API REST (como GDV)
djangorestframework==3.14.0
django-cors-headers==4.3.1

# Excel (para PESCO)
pandas==2.1.4
openpyxl==3.1.2
xlsxwriter==3.1.9

# PDF y Etiquetas (para PESCO)
reportlab==4.0.8
python-barcode==0.15.1
Pillow==10.1.0

# Deployment
gunicorn==21.2.0
whitenoise==6.6.0

# MCP Server para IA (para PESCO)
mcp-django==0.1.0

# Utilidades
pytz==2023.3
```

---

## 🔐 Archivo env_ejemplo.txt (Como GDV)

```bash
# env_ejemplo.txt
# Copiar a .env y completar con valores reales

# Django
SECRET_KEY=tu-secret-key-super-segura-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Supabase (PostgreSQL)
SUPABASE_URL=https://tu-proyecto.supabase.co
SUPABASE_KEY=tu-key-aqui
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=tu-password
DB_HOST=db.tu-proyecto.supabase.co
DB_PORT=5432

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=tu-email@pesco.cl
EMAIL_HOST_PASSWORD=tu-password

# MCP Server
MCP_ENABLED=True
MCP_PORT=8001
```

---

## 🚀 Script build.sh (Como GDV - Para Render)

```bash
#!/usr/bin/env bash
# build.sh - Script de deployment en Render

set -o errexit

# Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt

# Ejecutar migraciones
python manage.py migrate --noinput

# Colectar archivos estáticos
python manage.py collectstatic --noinput --clear

# Crear superusuario si no existe (opcional)
python manage.py shell << EOF
from core.models import Usuario
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@pesco.cl', 'cambiarpassword123')
    print('Superusuario creado')
else:
    print('Superusuario ya existe')
EOF

echo "✅ Build completado exitosamente"
```

---

## 🎯 Modelos Clave (Adaptados de GDV)

### core/models.py - Usuario

```python
from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    """
    Modelo de Usuario personalizado (como en GDV)
    """
    ROLES = [
        ('admin', 'Administrador'),
        ('bodega', 'Bodega'),
        ('despacho', 'Despacho'),
    ]
    
    rol = models.CharField(max_length=20, choices=ROLES, default='bodega')
    nombre_completo = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.get_rol_display()})"
    
    def es_admin(self):
        return self.rol == 'admin'
    
    def es_bodega(self):
        return self.rol == 'bodega'
    
    def es_despacho(self):
        return self.rol == 'despacho'
```

### solicitudes/models.py

```python
from django.db import models
from core.models import Usuario

class Solicitud(models.Model):
    """
    Modelo de Solicitud (similar a Producto en GDV)
    """
    TIPOS = [
        ('PC', 'PC'),
        ('OC', 'OC'),
        ('EM', 'Emergencia'),
        ('ST', 'Stock'),
        ('OF', 'Oficina'),
    ]
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_despacho', 'En Despacho'),
        ('embalado', 'Embalado'),
        ('despachado', 'Despachado'),
        ('cancelado', 'Cancelado'),
    ]
    
    # Campos
    fecha_solicitud = models.DateField(auto_now_add=True)
    hora_solicitud = models.TimeField(auto_now_add=True)
    tipo = models.CharField(max_length=2, choices=TIPOS)
    cliente = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, db_index=True)
    descripcion = models.TextField()
    cantidad_solicitada = models.IntegerField()
    bodega = models.CharField(max_length=50)
    observacion = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente', db_index=True)
    urgente = models.BooleanField(default=False, db_index=True)
    
    # Relaciones
    solicitante = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'solicitudes'
        ordering = ['-fecha_solicitud', '-hora_solicitud']
        verbose_name = 'Solicitud'
        verbose_name_plural = 'Solicitudes'
        indexes = [
            models.Index(fields=['estado', 'urgente']),
            models.Index(fields=['cliente']),
            models.Index(fields=['-fecha_solicitud']),
        ]
    
    def __str__(self):
        return f"Solicitud #{self.id} - {self.cliente} - {self.get_estado_display()}"
    
    def dias_desde_solicitud(self):
        from django.utils import timezone
        return (timezone.now().date() - self.fecha_solicitud).days
```

---

## 🔒 Decoradores de Seguridad (Como GDV)

### core/decorators.py

```python
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def role_required(allowed_roles):
    """
    Decorador para proteger vistas por rol
    Uso: @role_required(['admin', 'bodega'])
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.rol in allowed_roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("No tienes permisos para acceder a esta página")
        return wrapper
    return decorator

def admin_only(view_func):
    """
    Decorador para vistas solo de admin
    Uso: @admin_only
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.es_admin():
            return view_func(request, *args, **kwargs)
        return redirect('dashboard')
    return wrapper
```

---

## 📊 Vista de Dashboard (Como GDV)

### core/views.py

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from solicitudes.models import Solicitud
from django.db.models import Count

@login_required
def dashboard(request):
    """
    Dashboard principal (como en GDV)
    Muestra KPIs según el rol del usuario
    """
    user = request.user
    
    # KPIs comunes
    context = {
        'user': user,
    }
    
    if user.es_admin():
        # Admin ve todo
        context.update({
            'total_solicitudes': Solicitud.objects.count(),
            'solicitudes_pendientes': Solicitud.objects.filter(estado='pendiente').count(),
            'solicitudes_en_despacho': Solicitud.objects.filter(estado='en_despacho').count(),
            'solicitudes_urgentes': Solicitud.objects.filter(urgente=True, estado__in=['pendiente', 'en_despacho']).count(),
            'solicitudes_recientes': Solicitud.objects.all()[:10],
        })
    
    elif user.es_bodega():
        # Bodega solo ve pendientes
        context.update({
            'solicitudes_pendientes': Solicitud.objects.filter(estado='pendiente'),
            'mis_transferencias_hoy': user.transferencias.filter(fecha_transferencia__date=timezone.now().date()).count(),
        })
    
    elif user.es_despacho():
        # Despacho solo ve en despacho
        context.update({
            'solicitudes_en_despacho': Solicitud.objects.filter(estado='en_despacho'),
            'mis_embalajes_hoy': user.embalajes.filter(fecha_embalado__date=timezone.now().date()).count(),
        })
    
    return render(request, 'dashboard.html', context)
```

---

## 🎨 Template Base (Como GDV)

### frontend_django/templates/base.html

```django
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Sistema PESCO{% endblock %}</title>
    
    <!-- Bootstrap 5.3.0 -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css">
    
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    
    <!-- CSS Personalizado -->
    <link href="{% static 'css/custom.css' %}" rel="stylesheet">
    
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Navbar -->
    {% include 'components/navbar.html' %}
    
    <div class="container-fluid">
        <div class="row">
            <!-- Sidebar (opcional) -->
            {% if user.is_authenticated %}
            <nav class="col-md-2 d-none d-md-block bg-light sidebar">
                {% include 'components/sidebar.html' %}
            </nav>
            {% endif %}
            
            <!-- Contenido Principal -->
            <main class="col-md-10 ms-sm-auto px-4 py-4">
                <!-- Mensajes Flash -->
                {% if messages %}
                <div class="messages">
                    {% for message in messages %}
                    <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                <!-- Contenido de la página -->
                {% block content %}{% endblock %}
            </main>
        </div>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    
    <!-- JS Personalizado -->
    <script src="{% static 'js/app.js' %}"></script>
    
    {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## 🔄 URLs Principales (Como GDV)

### backend/urls.py

```python
from django.contrib import admin
from django.urls import path, include
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Core
    path('', core_views.dashboard, name='dashboard'),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    
    # Apps
    path('solicitudes/', include('solicitudes.urls')),
    path('bodega/', include('bodega.urls')),
    path('despacho/', include('despacho.urls')),
    path('guias/', include('guias.urls')),
    path('reportes/', include('reportes.urls')),
    
    # API (opcional)
    path('api/', include('api.urls')),
]
```

---

## 📋 Próximos Pasos

1. ✅ **Crear estructura de proyecto** basada en este documento
2. ✅ **Copiar archivos de configuración** (settings.py, urls.py)
3. ✅ **Implementar modelos** (Usuario, Solicitud, etc.)
4. ✅ **Crear templates base** con Bootstrap y colores PESCO
5. ✅ **Implementar decoradores** de seguridad
6. ✅ **Desarrollar dashboard** por roles
7. ✅ **Crear módulos** de bodega y despacho
8. ✅ **Implementar generación** de etiquetas PDF
9. ✅ **Deployment en Render**

---

## 📞 Referencias

- **Repositorio GDV**: https://github.com/CiroCortes/sistemaGDV
- **Bootstrap 5 Docs**: https://getbootstrap.com/docs/5.3/
- **Django Docs**: https://docs.djangoproject.com/en/5.0/
- **Supabase Docs**: https://supabase.com/docs

---

**Documento creado**: Noviembre 2025  
**Basado en**: sistemaGDV (sistema operativo y probado)  
**Adaptado para**: Sistema Logístico PESCO

