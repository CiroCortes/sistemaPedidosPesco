from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """
    Admin personalizado para el modelo Usuario
    Permite cambiar roles fácilmente desde el admin
    """
    list_display = ('username', 'nombre_completo_display', 'email', 'rol', 'rol_badge', 'is_active', 'date_joined')
    list_filter = ('rol', 'is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'nombre_completo', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    list_editable = ('rol', 'is_active')  # Permite editar rol directamente desde la lista
    
    # Campos visibles al editar un usuario existente
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Información PESCO', {
            'fields': ('rol', 'nombre_completo', 'telefono'),
            'description': 'Configura el rol del usuario y su información personal'
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Fechas Importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    # Campos visibles al crear un nuevo usuario
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Información Personal', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Información PESCO', {
            'fields': ('rol', 'nombre_completo', 'telefono'),
            'description': 'Asigna el rol del usuario: Admin (acceso total), Bodega o Despacho'
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
        }),
    )
    
    readonly_fields = ('last_login', 'date_joined')
    
    def nombre_completo_display(self, obj):
        """Muestra el nombre completo o username si no está configurado"""
        if obj.nombre_completo:
            return obj.nombre_completo
        elif obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        else:
            return f"{obj.username} (sin nombre)"
    nombre_completo_display.short_description = 'Nombre Completo'
    
    def rol_badge(self, obj):
        """Muestra el rol con un badge de color"""
        colors = {
            'admin': 'danger',      # Rojo para admin
            'bodega': 'warning',    # Amarillo para bodega
            'despacho': 'info',     # Azul para despacho
        }
        color = colors.get(obj.rol, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_rol_display()
        )
    rol_badge.short_description = 'Rol'
    rol_badge.admin_order_field = 'rol'
