# Solicitud de Desarrollo MVP – Sistema Logístico PESCO

## 📌 Contexto
La empresa **PESCO** utiliza actualmente **SAP en modo web** para la gestión de stock y reportería.  
Debido a la dificultad de acceder a queries rápidas, la operación logística se apoya en un **Excel compartido en SharePoint**, donde se registran solicitudes y movimientos diarios.

El flujo operativo se centra en tres áreas principales:
- **Bodega** (Entrega de mercadería a despacho)
- **Despacho** (Embalaje, pesaje y etiquetado)
- **Administración** (Emisión de guías SAP y registro final)

Actualmente, el registro manual en Excel genera problemas de eficiencia, duplicidad y errores humanos.

---

## 🎯 Objetivo del MVP
Construir un sistema web simple en **Python/Django**, con base de datos en **Supabase**, que permita:
1. **Registrar solicitudes** de manera ordenada y trazable.
2. **Manejar stock** mediante cargas temporales desde Excel (descargado de SAP).
3. **Evitar duplicidad de solicitudes** validando contra stock y pedidos pendientes.
4. **Generar informes exportables a Excel** para mantener compatibilidad con la operación actual.
5. **Proveer KPIs** (días en despacho, lead time) para análisis logístico.

---

## 🛠️ Requerimientos Funcionales

### 🔄 Flujo de Trabajo Completo

```
1. SOLICITUD INICIAL (Admin/Ventas)
        ↓
2. BODEGA → Entrega a Despacho
        ↓
3. DESPACHO → Embala, Pesa, Mide
        ↓
4. ADMIN → Emite Guía SAP + Registra OT
        ↓
5. DESPACHADO
```

---

### 1. Registro de Solicitudes (Admin)
**Usuario**: Admin (puede hacerlo también ventas/RRHH si se habilitan)

- ✅ **IMPLEMENTADO**: Ingreso manual de solicitudes: ventas, RRHH, EPP, emergencias, ambulancia, retiros de camión y **retiros urgentes de clientes**.
- **Campos principales**:
  - Fecha (recepción) - automática
  - Hora (registro) - automática
  - Tipo (PC, OC, EM, ST, OF, **RM**) - ✅ Implementado con todos los tipos
  - **Número de pedido** (PC/OF/EM/RM) - opcional, manual
  - **Número ST** (ST) - ✅ **Auto-generado** con formato `ST-AAAA-###`, reinicia cada año
  - Cliente
  - **Múltiples productos** - ✅ Implementado con `SolicitudDetalle` (hasta 45 líneas)
  - Código producto (puede ser "SC" para sin código)
  - Descripción
  - Cantidad solicitada
  - Bodega origen - ✅ **Opcional** (admin o IA la asignará después)
  - **Transporte** - ✅ Dropdown: Camión PESCO, Varmontt, Starken, Kaizen, Retira cliente, Otro
  - Observación
  - Urgente (checkbox)
- **Estado inicial**: `pendiente`
- ✅ **Formulario dinámico**: Inicia con 5 líneas de producto, botón "Agregar línea" para hasta 45 productos

---

### 2. Módulo de Bodega (Usuario Bodega)
**Usuario**: Bodega (acceso limitado)

**Función**: Registrar entrega de mercadería a Despacho

- **Campos a registrar**:
  - Número de transferencia (único)
  - Fecha de entrega
  - Hora de entrega
  - Productos entregados (lista con cantidades)
  - Observaciones (opcional)

- **Acciones**:
  - Ver solicitudes pendientes
  - Seleccionar solicitud(es) a procesar
  - Registrar número de transferencia
  - Confirmar entrega a despacho

- **Estado cambia a**: `en_despacho`

**Restricciones**: 
- ❌ No puede ver módulo de despacho
- ❌ No puede emitir guías
- ✅ Solo puede registrar transferencias

---

### 3. Módulo de Despacho (Usuario Despacho)
**Usuario**: Despacho (acceso limitado)

**Función**: Recibir mercadería, embalar, pesar, medir y etiquetar

- **Campos a registrar**:
  - Fecha/hora de embalado
  - Peso (kg)
  - Medidas (largo x ancho x alto en cm)
  - Número de bultos
  - Transporte (PESCO / EXTERNO)
  - Transportista (si es externo: Starken, Varmontt, etc.)
  - Observaciones

- **Acciones**:
  - Ver solicitudes "en_despacho"
  - Registrar datos de embalaje
  - Pesar productos
  - Medir bultos
  - **Generar e imprimir etiquetas de bultos** 
    - 📌 **Modelo de etiqueta pendiente** (será proporcionado por el usuario)
    - Sistema generará PDF para impresión
    - Incluirá: código producto, cliente, bulto X de Y, peso, medidas

- **Estado cambia a**: `embalado`

**Restricciones**:
- ❌ No puede ver módulo de bodega
- ❌ No puede emitir guías SAP
- ✅ Solo puede embalar y etiquetar

---

### 4. Módulo de Emisión de Guías (Solo Admin)
**Usuario**: **Solo Admin**

**Función**: Emitir guía en SAP y registrar números oficiales

- **Campos a registrar**:
  - Número de Guía de Despacho (de SAP)
  - Número(s) de OT (orden de trabajo/traslado)
  - Fecha/hora de emisión
  - Observaciones finales

- **Acciones**:
  - Ver solicitudes "embaladas"
  - Emitir guía en SAP (fuera del sistema)
  - Registrar número de guía en el sistema
  - Registrar número(s) de OT
  - Confirmar despacho final

- **Estado cambia a**: `despachado`

**Nota importante**: El admin emite la guía directamente en **SAP** (sistema externo) y solo **registra el número** en este sistema para trazabilidad.

---

### 5. Rol de Administrador (Acceso Total)
**Usuario**: Admin (tú)

**Privilegios especiales**:
- ✅ **Acceso a todos los módulos** (Bodega, Despacho, Guías)
- ✅ Puede completar cualquier paso del proceso
- ✅ Puede reemplazar a cualquier usuario si falta personal
- ✅ Puede hacer todo el flujo completo solo
- ✅ Acceso a reportes y KPIs
- ✅ Gestión de usuarios
- ✅ Configuración del sistema

**Casos de uso**:
- Si falta personal de bodega → Admin puede registrar transferencias
- Si falta personal de despacho → Admin puede embalar y etiquetar
- Admin siempre emite las guías SAP

---

### 6. KPIs Automáticos
- **Días en despacho**: Desde que bodega entrega hasta que admin emite guía
- **Lead time total**: Desde solicitud inicial hasta despacho final
- **Solicitudes urgentes**: Contador y tiempo promedio de respuesta
- **Eficiencia por área**: Tiempo promedio en bodega vs despacho

---

## 📊 Flujo de Estados del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO DE VIDA DE SOLICITUD                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐
│  PENDIENTE  │  ← Estado inicial (Admin crea solicitud)
└──────┬──────┘
       │ 📦 Usuario BODEGA registra:
       │    - Número transferencia
       │    - Fecha/hora entrega
       ↓
┌─────────────┐
│EN_DESPACHO  │  ← Esperando que Despacho procese
└──────┬──────┘
       │ 🚚 Usuario DESPACHO registra:
       │    - Peso, medidas
       │    - Número de bultos
       │    - Genera etiquetas
       ↓
┌─────────────┐
│  EMBALADO   │  ← Esperando que Admin emita guía
└──────┬──────┘
       │ 👤 Usuario ADMIN registra:
       │    - Guía SAP (emitida en SAP)
       │    - Número(s) OT
       ↓
┌─────────────┐
│ DESPACHADO  │  ← Estado final ✅
└─────────────┘

       ❌ CANCELADO ← Puede cancelarse en cualquier momento (solo Admin)
```

### Estados Detallados

| Estado | Color | Descripción | Quién puede cambiar |
|--------|-------|-------------|---------------------|
| `pendiente` | 🟡 Amarillo | Solicitud creada, esperando bodega | → Bodega |
| `en_despacho` | 🔵 Azul | Mercadería entregada a despacho | → Despacho |
| `embalado` | 🟢 Verde claro | Embalado y listo, falta guía | → Admin |
| `despachado` | 🟢 Verde | Completado con guía SAP | Estado final |
| `cancelado` | 🔴 Rojo | Solicitud cancelada | Solo Admin |

---

## 🗄️ Manejo de Base de Datos

### Supabase
- Usado para **registro de solicitudes y KPIs**.
- Ventajas:
  - Plan gratuito suficiente para ~20 solicitudes diarias (≈4,400 mensuales).
  - Escalable en caso de crecimiento.
- Contendrá tablas:
  - `solicitudes`
  - `bodega_transferencias`
  - `despachos`
  - `kpis`

### Excel (base temporal externa)
- Usado para **cargas masivas de stock y pedidos pendientes** desde SAP.
- Flujo:
  1. Cada mañana se descarga stock desde SAP.
  2. Se sube al sistema como archivo Excel/CSV.
  3. El sistema valida solicitudes contra stock/pedidos pendientes.
- No se almacena en Supabase para evitar costos elevados.

---

## 📊 Informes
- El sistema debe exportar reportes en **Excel** para:
  - Encargados de bodega
  - Despacho
  - Administración
- Reportes incluyen:
  - Solicitudes pendientes
  - Transferencias realizadas
  - Despachos emitidos
  - KPIs de tiempos

---

## 🔐 Roles y Permisos

### Roles del Sistema

1. **👤 Admin (Tú)** → Acceso total, puede hacer TODO:
   - Crear solicitudes
   - Registrar transferencias de bodega
   - Embalar y etiquetar en despacho
   - **Emitir guías SAP y registrar OT**
   - Ver reportes y KPIs
   - Gestionar usuarios

2. **📦 Bodega** → Acceso limitado:
   - Ver solicitudes pendientes
   - Registrar transferencias a despacho
   - Ver historial de sus transferencias

3. **🚚 Despacho** → Acceso limitado:
   - Ver solicitudes en despacho
   - Registrar embalaje, peso, medidas
   - Generar e imprimir etiquetas de bultos
   - Ver historial de sus despachos

---

## 🚀 Alcance del MVP
1. **Ingreso de solicitudes manuales** con validación contra stock cargado desde Excel.  
2. **Dashboard en tabla simple** mostrando estados (pendiente, listo, embalado, despachado, urgente).  
3. **Carga de stock/pedidos pendientes vía Excel/CSV**.  
4. **Exportación de reportes a Excel**.  
5. **KPIs básicos**: días en despacho y lead time.  

---

## 🛠️ Stack Tecnológico

### Backend
- **Python 3.11+**
- **Django 5.0+** (Framework principal)
- **Supabase** (Base de datos PostgreSQL)
  - Índices optimizados para consultas rápidas
  - Plan gratuito: 500MB storage, 50K usuarios activos
- **Django REST Framework** (APIs)
- **MCP Server** (Model Context Protocol para integración con IA)
  - Biblioteca: `mcp-django`
  - Permite interacción con asistentes de IA

### Frontend
- **Bootstrap 5** (Framework CSS responsivo)
- **JavaScript (ES6+)** (Interactividad)
- **Django Templates** (Renderizado del lado del servidor)
- **Componentes modulares reutilizables** (evitar código repetitivo)

### Gestión de Datos
- **Pandas** (Procesamiento de archivos Excel/CSV)
- **openpyxl** (Lectura y escritura de Excel)
- **Cookies** (Caché de consultas frecuentes para reducir carga en DB)

### Deployment
- **Render** (Hosting web gratuito/pago)
- **Gunicorn** (Servidor WSGI)
- **WhiteNoise** (Archivos estáticos)

---

## 🎨 Diseño UI/UX

### Paleta de Colores
Basada en dashboard corporativo profesional:
- **Azul Principal**: `#00B4D8` (turquesa/celeste) - Elementos principales, navbar
- **Verde**: `#4CAF50` - Estados completados, alertas positivas
- **Amarillo**: `#FFC107` - Estados pendientes, advertencias
- **Rojo**: `#F44336` - Estados cancelados, alertas críticas
- **Gris**: `#6C757D` - Texto secundario
- **Blanco**: `#FFFFFF` - Fondos de tarjetas

### Componentes UI
- **Dashboard con KPIs** (tarjetas métricas con iconos)
- **Tablas responsivas** con paginación
- **Formularios validados** con feedback visual
- **Filtros dinámicos** sin recargar página
- **Notificaciones toast** para acciones del usuario
- **Exportación a Excel** con un clic

---

## 🏗️ Arquitectura del Sistema

### ✅ Estructura del Proyecto Implementada

```
sistemaPesco/
├── backend/                  # Configuración Django
│   ├── settings.py          # Settings con Supabase, Gemini, etc.
│   ├── urls.py              # URLs principales
│   └── wsgi.py
│
├── core/                    # App central ✅ IMPLEMENTADO
│   ├── models.py           # Usuario (rol: admin/bodega/despacho)
│   ├── views.py            # Dashboard, login, logout, perfil
│   ├── decorators.py       # @role_required
│   ├── admin.py            # Admin personalizado
│   └── templates/
│       ├── dashboard.html
│       ├── login.html
│       └── perfil.html
│
├── solicitudes/            # Módulo de solicitudes ✅ IMPLEMENTADO
│   ├── models.py          # Solicitud + SolicitudDetalle
│   ├── views.py           # CRUD + API IA
│   ├── forms.py           # SolicitudForm + SolicitudDetalleFormSet
│   ├── services.py        # crear_solicitud_desde_payload()
│   ├── urls.py
│   └── templates/
│       ├── lista.html
│       ├── formulario.html
│       └── detalle.html
│
├── ia/                     # Módulo de IA ✅ IMPLEMENTADO
│   ├── gemini_client.py   # call_gemini_for_solicitud()
│   ├── views.py          # ia_chat (vista web)
│   ├── urls.py
│   └── templates/
│       └── chat.html
│
├── frontend_django/        # Templates globales ✅ IMPLEMENTADO
│   └── templates/
│       ├── base.html
│       └── components/
│           ├── navbar.html
│           └── sidebar.html
│
├── mcp_server.py          # Servidor MCP ✅ IMPLEMENTADO
├── test/                  # Tests
│   └── test_gemini.py
├── manage.py
├── requirements.txt
├── .env.example
└── README.md
```

### Arquitectura Modular (Inspirada en sistemaGDV)

```
sistemaPesco/
├── config/                  # Configuración Django
│   ├── settings/
│   │   ├── base.py         # Settings comunes
│   │   ├── development.py  # Settings desarrollo
│   │   └── production.py   # Settings producción
│   ├── urls.py
│   └── wsgi.py
│
├── apps/                    # Aplicaciones modulares
│   ├── core/               # Funcionalidades centrales
│   │   ├── models.py      # Usuario, etc.
│   │   ├── views.py       # Dashboard, login
│   │   ├── decorators.py  # @role_required
│   │   └── templates/
│   │       └── dashboard.html
│   │
│   ├── solicitudes/        # Módulo de solicitudes (Admin)
│   │   ├── models.py      # Modelo Solicitud
│   │   ├── views.py       # CRUD solicitudes
│   │   ├── forms.py       # Formularios
│   │   ├── urls.py
│   │   └── templates/
│   │       ├── solicitud_lista.html
│   │       └── solicitud_form.html
│   │
│   ├── bodega/             # Módulo de bodega
│   │   ├── models.py      # Modelo Transferencia
│   │   ├── views.py       # Vista solo para bodega
│   │   ├── forms.py       # Form transferencia
│   │   └── templates/
│   │       └── bodega_panel.html
│   │
│   ├── despacho/           # Módulo de despacho
│   │   ├── models.py      # Modelo Embalaje
│   │   ├── views.py       # Vista solo para despacho
│   │   ├── forms.py       # Form embalaje
│   │   ├── etiquetas.py   # Generación de etiquetas PDF
│   │   └── templates/
│   │       ├── despacho_panel.html
│   │       └── etiqueta_bulto.html
│   │
│   ├── guias/              # Módulo de guías SAP (Solo Admin)
│   │   ├── views.py       # Registro de guías
│   │   ├── forms.py       # Form guía + OT
│   │   └── templates/
│   │       └── guias_panel.html
│   │
│   ├── reportes/           # Módulo de reportes y KPIs
│   │   ├── views.py
│   │   ├── exporters.py   # Lógica de exportación Excel
│   │   ├── kpis.py        # Cálculo de KPIs
│   │   └── templates/
│   │       └── reportes.html
│   │
│   └── stock/              # Módulo de gestión de stock (opcional)
│       ├── models.py      # Caché de stock
│       ├── importers.py   # Carga desde Excel
│       └── validators.py  # Validación contra SAP
│
├── static/                  # Archivos estáticos
│   ├── css/
│   │   ├── bootstrap.min.css
│   │   └── custom.css     # Estilos personalizados
│   ├── js/
│   │   ├── bootstrap.bundle.min.js
│   │   └── app.js         # JavaScript global
│   └── img/
│
├── templates/              # Templates globales
│   ├── base.html          # Template base (navbar, footer)
│   ├── dashboard.html     # Dashboard principal
│   └── components/        # Componentes reutilizables
│       ├── card_kpi.html
│       ├── table.html
│       └── form_modal.html
│
├── utils/                  # Utilidades compartidas
│   ├── decorators.py
│   ├── helpers.py
│   └── validators.py
│
├── mcp/                    # Servidor MCP para IA
│   ├── server.py
│   └── tools.py
│
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
│
├── .env.example
├── manage.py
└── README.md
```

### Principios de Arquitectura
1. **Separación de responsabilidades** (SoC)
2. **DRY (Don't Repeat Yourself)** - Componentes reutilizables
3. **Modularidad** - Cada app Django es independiente
4. **Escalabilidad** - Fácil agregar nuevos módulos
5. **Mantenibilidad** - Código limpio y documentado

---

## 🗄️ Estructura de Base de Datos (Supabase)

### Tablas Principales

#### `solicitudes`
```sql
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    fecha_solicitud DATE NOT NULL,
    hora_solicitud TIME NOT NULL,
    tipo VARCHAR(2) CHECK (tipo IN ('PC', 'OC', 'EM', 'ST', 'OF', 'RM')),
    numero_pedido VARCHAR(50), -- Opcional para PC/OF/EM/RM
    numero_st VARCHAR(20), -- Auto-generado para ST (formato: ST-AAAA-###)
    cliente VARCHAR(200),
    codigo VARCHAR(50), -- Código del primer producto (legacy)
    descripcion TEXT, -- Descripción del primer producto (legacy)
    cantidad_solicitada INTEGER, -- Cantidad del primer producto (legacy)
    bodega VARCHAR(50), -- Opcional (puede quedar vacío)
    transporte VARCHAR(20) DEFAULT 'PESCO' CHECK (transporte IN ('PESCO', 'VARMONTT', 'STARKEN', 'KAIZEN', 'RETIRA_CLIENTE', 'OTRO')),
    observacion TEXT,
    estado VARCHAR(20) DEFAULT 'pendiente' CHECK (estado IN ('pendiente', 'en_despacho', 'embalado', 'despachado', 'cancelado')),
    urgente BOOLEAN DEFAULT FALSE,
    solicitante_id INTEGER REFERENCES usuarios(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices para optimización
CREATE INDEX idx_solicitudes_fecha ON solicitudes(fecha_solicitud DESC);
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_codigo ON solicitudes(codigo);
CREATE INDEX idx_solicitudes_urgente ON solicitudes(urgente);
CREATE INDEX idx_solicitudes_cliente ON solicitudes(cliente);
CREATE INDEX idx_solicitudes_tipo_created ON solicitudes(tipo, created_at);

-- Comentarios sobre estados:
-- pendiente: Solicitud creada, esperando bodega
-- en_despacho: Bodega entregó a despacho
-- embalado: Despacho terminó de embalar
-- despachado: Admin emitió guía SAP
-- cancelado: Solicitud cancelada
```

#### `solicitudes_detalle`
```sql
CREATE TABLE solicitudes_detalle (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER REFERENCES solicitudes(id) ON DELETE CASCADE,
    codigo VARCHAR(50) NOT NULL,
    descripcion TEXT,
    cantidad INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_solicitudes_detalle_solicitud ON solicitudes_detalle(solicitud_id, codigo);
```

**Nota**: Las solicitudes pueden tener múltiples productos (hasta 45 líneas). Los campos `codigo`, `descripcion`, `cantidad_solicitada` en la tabla `solicitudes` se mantienen por compatibilidad con solicitudes antiguas que no usan `solicitudes_detalle`.

#### `bodega_transferencias`
```sql
CREATE TABLE bodega_transferencias (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER REFERENCES solicitudes(id) ON DELETE CASCADE,
    numero_transferencia VARCHAR(50) UNIQUE NOT NULL,
    fecha_transferencia DATE NOT NULL,
    hora_transferencia TIME NOT NULL,
    encargado_id INTEGER REFERENCES usuarios(id),
    observaciones TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_transferencias_solicitud ON bodega_transferencias(solicitud_id);
CREATE INDEX idx_transferencias_fecha ON bodega_transferencias(fecha_transferencia DESC);
```

#### `despachos`
```sql
CREATE TABLE despachos (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER REFERENCES solicitudes(id) ON DELETE CASCADE,
    
    -- Datos de embalaje (registrados por Despacho)
    fecha_embalado DATE NOT NULL,
    hora_embalado TIME NOT NULL,
    peso DECIMAL(10,2), -- kg
    medidas VARCHAR(50), -- formato: "largo x ancho x alto cm"
    numero_bultos INTEGER DEFAULT 1,
    transporte VARCHAR(20) CHECK (transporte IN ('PESCO', 'EXTERNO')),
    transportista VARCHAR(100), -- Si es externo: Starken, Varmontt, etc.
    encargado_embalaje_id INTEGER REFERENCES usuarios(id),
    observaciones_embalaje TEXT,
    
    -- Datos de guía SAP (registrados por Admin)
    guia_despacho VARCHAR(50) UNIQUE, -- Número de guía SAP (nullable hasta que admin la emite)
    numero_ot VARCHAR(200), -- Puede ser múltiples OTs separados por comas
    fecha_guia DATE,
    hora_guia TIME,
    admin_emisor_id INTEGER REFERENCES usuarios(id),
    observaciones_guia TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_despachos_solicitud ON despachos(solicitud_id);
CREATE INDEX idx_despachos_fecha_embalado ON despachos(fecha_embalado DESC);
CREATE INDEX idx_despachos_fecha_guia ON despachos(fecha_guia DESC);
CREATE INDEX idx_despachos_guia ON despachos(guia_despacho);
CREATE INDEX idx_despachos_transporte ON despachos(transporte);
```

#### `kpis`
```sql
CREATE TABLE kpis (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER REFERENCES solicitudes(id) ON DELETE CASCADE,
    dias_en_despacho INTEGER,
    lead_time_horas DECIMAL(10,2),
    calculado_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_kpis_solicitud ON kpis(solicitud_id);
```

#### `usuarios`
```sql
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL, -- Hash de contraseña
    email VARCHAR(254) UNIQUE NOT NULL,
    nombre_completo VARCHAR(200),
    rol VARCHAR(20) CHECK (rol IN ('admin', 'bodega', 'despacho')),
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_usuarios_rol ON usuarios(rol);
CREATE INDEX idx_usuarios_username ON usuarios(username);

-- Usuario admin por defecto (password debe ser hasheado)
INSERT INTO usuarios (username, email, nombre_completo, rol, is_active) 
VALUES ('admin', 'admin@pesco.cl', 'Administrador Principal', 'admin', TRUE);
```

---

## 🔐 Sistema de Autenticación y Permisos

### Roles y Accesos Detallados
| Rol | Crear Solicitud | Registrar Transferencia | Embalar/Pesar/Medir | Emitir Guía SAP | Reportes | KPIs | Gestión Usuarios |
|-----|----------------|------------------------|---------------------|-----------------|----------|------|------------------|
| **👤 Admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **📦 Bodega** | ❌ | ✅ | ❌ | ❌ | ⚠️ Solo sus transferencias | ❌ | ❌ |
| **🚚 Despacho** | ❌ | ❌ | ✅ | ❌ | ⚠️ Solo sus despachos | ❌ | ❌ |

**Nota importante**: Solo el **Admin** puede emitir guías SAP y tener acceso completo a todos los módulos.

### Implementación
```python
# utils/decorators.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

def role_required(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.rol in allowed_roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("No tienes permisos para acceder")
        return wrapper
    return decorator
```

---

## 🤖 Integración con Inteligencia Artificial

### ✅ Asistente IA Integrado en la Web

El sistema incluye un **Asistente IA** integrado directamente en la aplicación web, accesible desde el menú lateral para usuarios Admin.

**Funcionalidades**:
- ✅ **Procesamiento de texto**: Pega el contenido de un correo electrónico y la IA extrae automáticamente:
  - Tipo de solicitud (PC, OF, EM, RM, ST)
  - Número de pedido (si aplica)
  - Cliente
  - Códigos de productos y cantidades
  - Observaciones adicionales (direcciones de entrega, instrucciones de facturación, etc.)
- ✅ **Procesamiento de imágenes**: Sube capturas de pantalla de SAP y la IA:
  - Identifica números de pedido
  - Extrae códigos de productos y cantidades
  - Genera automáticamente la solicitud completa

**Tecnología**: 
- **Gemini 2.5 Flash** (`google-generativeai`)
- Modelo configurado con prompt especializado para extracción de datos logísticos
- Integración directa con el sistema de creación de solicitudes

**Ubicación**: `/ia/chat/` (requiere autenticación y rol Admin)

### ✅ API Endpoint para Agentes IA Externos

**Endpoint**: `POST /solicitudes/api/ia/crear/`

**Autenticación**: Token API (`X-API-TOKEN` o `Authorization: Bearer`)

**Payload JSON**:
```json
{
  "tipo": "PC",
  "numero_pedido": "25111045",
  "cliente": "SUC LOS ANGELES",
  "bodega": "013-01",
  "transporte": "Camión PESCO",
  "estado": "pendiente",
  "urgente": false,
  "observacion": "Entregar en dirección...",
  "productos": [
    {"codigo": "3502040", "descripcion": "CILINDRO", "cantidad": 5},
    {"codigo": "3502021", "descripcion": "VALVULA", "cantidad": 2}
  ]
}
```

**Respuesta**:
```json
{
  "ok": true,
  "id": 123,
  "tipo": "PC",
  "numero_pedido": "25111045",
  "cliente": "SUC LOS ANGELES",
  "estado": "pendiente"
}
```

### ✅ MCP Server (Model Context Protocol)

**Archivo**: `mcp_server.py` (raíz del proyecto)

**Herramientas expuestas**:
- `ping()`: Verificación de conectividad
- `crear_solicitud(payload_json)`: Crear solicitud desde JSON

**Configuración**:
```bash
pip install mcp django
```

**Ejecución**:
```bash
python mcp_server.py
```

**Uso con IA Externa**:
Permite que asistentes de IA (Claude Desktop, ChatGPT con plugins MCP, etc.) interactúen directamente con el sistema para:
- ✅ Crear solicitudes automáticamente desde correos o imágenes
- Consultar solicitudes pendientes (pendiente)
- Generar reportes automáticos (pendiente)
- Análisis predictivo de stock (pendiente)

### Configuración de Variables de Entorno

**`.env`**:
```bash
GEMINI_API_KEY=tu_api_key_de_google_ai_studio
GEMINI_MODEL=gemini-2.5-flash
IA_API_TOKEN=tu_token_secreto_para_api
```

**⚠️ IMPORTANTE**: 
- La API key de Gemini debe obtenerse desde **Google AI Studio** (https://aistudio.google.com)
- No usar API keys genéricas de Google Cloud (no son compatibles)

---

## ⚡ Optimizaciones de Rendimiento

### 1. Índices en Supabase
- Ya definidos en estructura de tablas
- Mejoran velocidad de consultas en 70-90%

### 2. Cookies para Caché
```python
# utils/cache.py
from django.core.cache import cache

def get_stock_cache(bodega):
    cache_key = f'stock_{bodega}'
    stock = cache.get(cache_key)
    if not stock:
        stock = cargar_stock_desde_excel(bodega)
        cache.set(cache_key, stock, timeout=3600)  # 1 hora
    return stock
```

### 3. Queries Optimizadas
```python
# Usar select_related y prefetch_related
solicitudes = Solicitud.objects.select_related(
    'solicitante', 'bodega_transferencia', 'despacho'
).prefetch_related('kpis')
```

### 4. Paginación
```python
# views.py
from django.core.paginator import Paginator

def lista_solicitudes(request):
    solicitudes = Solicitud.objects.all().order_by('-fecha_solicitud')
    paginator = Paginator(solicitudes, 25)  # 25 por página
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'solicitudes/lista.html', {'page': page})
```

---

## 📊 Dashboard y Visualización

### KPIs Principales (Tarjetas)
1. **Niveles de Inventario** 📦
   - Total items en stock
   - Variación respecto al mes pasado

2. **Órdenes Pendientes** 📋
   - Número de órdenes sin procesar
   - Órdenes urgentes destacadas

3. **Envíos Hoy** 🚚
   - Preparados para despacho
   - En tránsito

4. **Alertas Críticas** ⚠️
   - Stock bajo límite
   - Retrasos en despacho

### Tabla de Actividad Reciente
- Estados con colores (completado=verde, pendiente=amarillo, cancelado=rojo)
- Filtros por cliente, estado, fecha
- Exportación directa a Excel

---

## 🏷️ Sistema de Etiquetas de Bultos

### Funcionalidad
El módulo de Despacho debe poder generar e imprimir etiquetas para cada bulto embalado.

### Datos en la Etiqueta (Pendiente definir formato exacto)
- **Número de bulto**: "Bulto 1 de 3"
- **Código de producto**: SKU o código interno
- **Cliente**: Nombre o razón social
- **Peso**: En kilogramos
- **Medidas**: Largo x Ancho x Alto (cm)
- **Fecha de embalaje**
- **Código de barras o QR** (opcional): Para tracking

### Implementación Técnica
```python
# apps/despacho/etiquetas.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def generar_etiqueta_bulto(solicitud, numero_bulto, total_bultos, peso, medidas):
    """
    Genera un PDF con la etiqueta del bulto
    """
    filename = f'etiqueta_{solicitud.id}_bulto_{numero_bulto}.pdf'
    c = canvas.Canvas(filename, pagesize=A4)
    
    # Diseño de la etiqueta (pendiente modelo del usuario)
    c.drawString(100, 750, f"PESCO - Sistema Logístico")
    c.drawString(100, 700, f"Cliente: {solicitud.cliente}")
    c.drawString(100, 650, f"Producto: {solicitud.codigo} - {solicitud.descripcion}")
    c.drawString(100, 600, f"Bulto: {numero_bulto} de {total_bultos}")
    c.drawString(100, 550, f"Peso: {peso} kg")
    c.drawString(100, 500, f"Medidas: {medidas}")
    
    # Código de barras (opcional)
    # Implementar con librería python-barcode
    
    c.save()
    return filename
```

### Biblioteca Requerida
```bash
pip install reportlab python-barcode
```

### Flujo de Uso
1. Usuario Despacho ingresa datos de embalaje
2. Sistema pregunta: "¿Cuántos bultos?"
3. Sistema genera un PDF con todas las etiquetas
4. Usuario descarga e imprime las etiquetas
5. Etiquetas se adhieren físicamente a los bultos

**📌 Nota**: El formato final de la etiqueta será proporcionado por el usuario.

---

## 📦 Requirements

### base.txt
```
Django>=5.0
psycopg2-binary>=2.9
supabase>=2.0
python-dotenv>=1.0
pandas>=2.0
openpyxl>=3.1
xlsxwriter>=3.1
reportlab>=4.0
python-barcode>=0.15
djangorestframework>=3.14
django-cors-headers>=4.3
gunicorn>=21.0
whitenoise>=6.6
mcp>=0.1.0
google-generativeai>=0.3.0
Pillow>=10.0
```

### development.txt
```
-r base.txt
django-debug-toolbar>=4.2
black>=23.0
flake8>=6.0
```

---

## 🚀 Instalación y Configuración

### 1. Clonar repositorio
```bash
git clone https://github.com/tuusuario/sistemaPesco.git
cd sistemaPesco
```

### 2. Crear entorno virtual
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Instalar dependencias
```bash
pip install -r requirements/development.txt
```

### 4. Configurar variables de entorno
```bash
cp .env.example .env
# Editar .env con:
# - SECRET_KEY (generar uno nuevo para producción)
# - DEBUG=True (desarrollo)
# - GEMINI_API_KEY (obtener de https://aistudio.google.com)
# - GEMINI_MODEL=gemini-2.5-flash
# - IA_API_TOKEN (token secreto para API de IA)
# - Credenciales de Supabase (cuando se configure)
```

### 5. Ejecutar migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Crear superusuario
```bash
python manage.py createsuperuser
```

### 7. Ejecutar servidor
```bash
python manage.py runserver
```

### 8. Ejecutar MCP Server (opcional, en otra terminal)
```bash
python mcp_server.py
```

### 9. Acceder al Asistente IA
- Inicia sesión como Admin
- Ve al menú lateral → "Asistente IA"
- Pega texto de correo o sube imagen de SAP
- La IA procesará y creará la solicitud automáticamente

---

## 🔧 Archivos Clave Implementados

### Backend

**`solicitudes/models.py`**:
- `Solicitud`: Modelo principal con auto-generación de números ST
- `SolicitudDetalle`: Líneas de producto (hasta 45 por solicitud)
- Métodos helper: `total_codigos()`, `_generar_numero_st()`, etc.

**`solicitudes/services.py`**:
- `crear_solicitud_desde_payload()`: Función centralizada para crear solicitudes desde JSON
- Maneja validaciones, normalización de datos, creación de detalles
- Reutilizable desde vistas web, API y MCP

**`solicitudes/views.py`**:
- `lista_solicitudes`: Listado con filtros por rol y búsqueda
- `crear_solicitud`: Maneja formulario + formset dinámico
- `detalle_solicitud`: Vista detallada con productos
- `api_crear_solicitud_ia`: Endpoint REST para agentes IA

**`ia/gemini_client.py`**:
- `call_gemini_for_solicitud()`: Integración con Gemini 2.5 Flash
- Procesa texto e imágenes
- Retorna JSON estructurado para crear solicitudes

**`mcp_server.py`**:
- Servidor MCP standalone
- Expone herramientas: `ping()`, `crear_solicitud()`
- Inicializa Django automáticamente

### Frontend

**`frontend_django/templates/components/sidebar.html`**:
- Menú dinámico según rol del usuario
- Incluye enlace "Asistente IA" para Admin

**`solicitudes/templates/formulario.html`**:
- Formulario con JavaScript para agregar líneas dinámicamente
- Inicia con 5 líneas, expandible hasta 45

**`solicitudes/templates/lista.html`**:
- Tabla responsiva con columnas optimizadas
- Búsqueda por número de pedido/ST
- Muestra contador de códigos por solicitud

### Configuración

**`backend/settings.py`**:
- Configuración de Gemini (`GEMINI_API_KEY`, `GEMINI_MODEL`)
- Token API para endpoint IA (`IA_API_TOKEN`)
- CORS y REST Framework configurados
- Base de datos configurada (SQLite dev, Supabase pendiente)

---

## 📌 Próximos pasos

### Fase 1: Configuración Inicial ⚙️
- [x] Definir estructura de tablas en Supabase  
- [x] Definir roles y flujo de trabajo
- [x] Crear proyecto Django con arquitectura modular  
- [x] Configurar base de datos (SQLite para desarrollo, Supabase pendiente)
- [x] Implementar sistema de autenticación por roles  

### Fase 2: Desarrollo del Core 🏗️
- [x] Desarrollar dashboard principal con Bootstrap 5  
- [x] Implementar modelo de Solicitudes con múltiples productos
- [x] Crear formularios de ingreso con validación y formsets dinámicos
- [x] Aplicar paleta de colores corporativa (azul turquesa)
- [x] Implementar auto-generación de números ST
- [x] Sistema de cambio de rol desde UI (Admin)

### Fase 3: Módulos Operativos 📦🚚
- [ ] Desarrollar módulo de Bodega (registro de transferencias)
- [ ] Desarrollar módulo de Despacho (embalaje, peso, medidas)
- [ ] Implementar generación de etiquetas de bultos (PDF)
- [ ] Desarrollar módulo de Guías SAP (solo Admin)

### Fase 4: Reportes y Analytics 📊
- [ ] Implementar cálculo automático de KPIs
- [ ] Crear sistema de exportación de reportes a Excel
- [x] Dashboard con KPIs básicos por rol
- [ ] Configurar carga de stock desde Excel con caché

### Fase 5: Optimización y AI 🤖
- [x] Integrar MCP Server para IA  
- [x] Implementar Asistente IA integrado en web (Gemini 2.5)
- [x] API endpoint para agentes IA externos
- [x] Optimizar queries con índices en modelos
- [ ] Implementar sistema de cookies para caché

### Fase 6: Testing y Producción 🚀
- [ ] Probar flujo completo con usuarios internos  
- [x] Ajustes de UX/UI según feedback (listado, formularios dinámicos)
- [ ] Configurar conexión Supabase en producción
- [ ] Deploy en Render (producción)  
- [x] Documentación técnica actualizada

---

## 📋 Resumen Ejecutivo del Sistema

### 🎯 Problema
Registro manual en Excel genera ineficiencias, duplicidad y errores en la operación logística de PESCO.

### 💡 Solución
Sistema web Django con Supabase que digitaliza el flujo completo: Solicitud → Bodega → Despacho → Guía SAP.

### 👥 Usuarios (3 Roles)
1. **Admin**: Acceso total, emite guías SAP, puede reemplazar cualquier rol
2. **Bodega**: Registra transferencias a despacho
3. **Despacho**: Embala, pesa, mide y genera etiquetas

### 🔄 Flujo Simplificado
```
Admin crea solicitud → Bodega registra transferencia → 
Despacho embala y etiqueta → Admin emite guía SAP → Despachado ✅
```

### 🎨 Tecnologías
- **Backend**: Python + Django 5 + Supabase (PostgreSQL) / SQLite (desarrollo)
- **Frontend**: Bootstrap 5 + JavaScript + Django Templates
- **IA**: Gemini 2.5 Flash (`google-generativeai`)
- **Extras**: MCP Server (IA), ReportLab (etiquetas PDF), Pandas (Excel)

### 📈 Beneficios Implementados
- ✅ Trazabilidad completa de solicitudes
- ✅ Eliminación de duplicidad de registros
- ✅ **Asistente IA integrado** para procesar correos e imágenes automáticamente
- ✅ **Múltiples productos por solicitud** (hasta 45 líneas)
- ✅ **Auto-generación de números ST** con reinicio anual
- ✅ Dashboard con KPIs por rol
- ✅ Acceso por roles (seguridad)
- ✅ Formularios dinámicos con JavaScript
- ✅ API REST para integraciones externas

### 📈 Beneficios Pendientes
- ⏳ KPIs automáticos (lead time, días en despacho)
- ⏳ Reportes exportables a Excel
- ⏳ Generación automática de etiquetas de bultos

---

## 📞 Contacto y Soporte

**Administrador del Sistema**: [Tu nombre]  
**Email**: admin@pesco.cl  
**Repositorio**: [GitHub del proyecto]  

---

**Versión del Documento**: 3.0  
**Última Actualización**: Diciembre 2024  
**Estado**: ✅ **MVP en desarrollo activo** - Módulo de Solicitudes + IA implementado

---

## 📝 Changelog de Implementación

### Versión 3.0 (Diciembre 2024) - Módulo de Solicitudes + IA
- ✅ Sistema de autenticación con roles (Admin, Bodega, Despacho)
- ✅ Modelo `Solicitud` completo con todos los campos
- ✅ Modelo `SolicitudDetalle` para múltiples productos (hasta 45 líneas)
- ✅ Auto-generación de números ST (`ST-AAAA-###`) con reinicio anual
- ✅ Formularios dinámicos con formsets (inicia con 5 líneas, expandible)
- ✅ Dashboard con KPIs por rol
- ✅ Listado de solicitudes con búsqueda por pedido/ST
- ✅ Vista de detalle de solicitud
- ✅ **Asistente IA integrado** (`/ia/chat/`) con Gemini 2.5 Flash
- ✅ Procesamiento de texto (correos) e imágenes (capturas SAP)
- ✅ API endpoint para agentes IA externos (`/solicitudes/api/ia/crear/`)
- ✅ MCP Server implementado (`mcp_server.py`)
- ✅ Capa de servicios (`solicitudes/services.py`) para lógica reutilizable
- ✅ Cambio de rol desde UI (Admin)
- ✅ Templates Bootstrap 5 con diseño profesional
- ✅ Sistema de migraciones Django configurado

### Próximas Funcionalidades
- ⏳ Módulo de Bodega (transferencias)
- ⏳ Módulo de Despacho (embalaje, etiquetas)
- ⏳ Módulo de Guías SAP
- ⏳ Exportación de reportes a Excel
- ⏳ Cálculo automático de KPIs
- ⏳ Conexión Supabase en producción
