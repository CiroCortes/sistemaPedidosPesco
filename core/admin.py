from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Bodega

@admin.register(Usuario)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'nombre_completo', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'groups')
    fieldsets = UserAdmin.fieldsets + (
        ('Información Adicional', {'fields': ('rol', 'nombre_completo', 'telefono', 'bodegas_asignadas')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Adicional', {'fields': ('rol', 'nombre_completo', 'telefono', 'bodegas_asignadas')}),
    )
    filter_horizontal = ('bodegas_asignadas', 'groups', 'user_permissions')

@admin.register(Bodega)
class BodegaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'activa')
    search_fields = ('codigo', 'nombre')
    list_filter = ('activa',)
