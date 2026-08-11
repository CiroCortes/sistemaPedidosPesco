from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Bodega(models.Model):
    """
    Modelo de Bodega para el sistema.
    Representa las bodegas físicas donde se almacenan productos.
    """
    
    codigo = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código de bodega',
        help_text='Ej: 013-01, 013-PP, etc.'
    )
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre de la bodega'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    activa = models.BooleanField(
        default=True,
        verbose_name='¿Activa?'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creada el'
    )
    
    class Meta:
        db_table = 'bodegas'
        verbose_name = 'Bodega'
        verbose_name_plural = 'Bodegas'
        ordering = ['codigo']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['activa']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Usuario(AbstractUser):
    """
    Modelo de Usuario personalizado para Sistema PESCO
    Basado en la arquitectura de sistemaGDV
    
    Roles:
    - admin: Acceso total, puede hacer todo
    - bodega: Solo registra transferencias
    - despacho: Solo embala y etiqueta
    """
    
    ROLES = [
        ('admin', 'Administrador'),
        ('bodega', 'Bodega'),
        ('despacho', 'Despacho'),
    ]
    
    # Campos personalizados
    rol = models.CharField(
        max_length=20, 
        choices=ROLES, 
        default='bodega',
        verbose_name='Rol del usuario'
    )
    nombre_completo = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name='Nombre completo'
    )
    telefono = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name='Teléfono'
    )
    
    # Bodegas asignadas (múltiples bodegas por usuario)
    bodegas_asignadas = models.ManyToManyField(
        Bodega,
        blank=True,
        related_name='usuarios',
        verbose_name='Bodegas asignadas',
        help_text='Bodegas que este usuario puede gestionar'
    )
    
    # Timestamps
    fecha_creacion = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha de creación'
    )
    ultima_modificacion = models.DateTimeField(
        auto_now=True,
        verbose_name='Última modificación'
    )
    
    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['rol']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.nombre_completo} ({self.get_rol_display()})"
    
    # Métodos de ayuda
    def es_admin(self):
        """Retorna True si el usuario es administrador o superusuario"""
        return self.rol == 'admin' or self.is_superuser
    
    def es_bodega(self):
        """Retorna True si el usuario es de bodega"""
        return self.rol == 'bodega'
    
    def es_despacho(self):
        """Retorna True si el usuario es de despacho"""
        return self.rol == 'despacho'
    
    def puede_crear_solicitudes(self):
        """Solo admin puede crear solicitudes"""
        return self.es_admin()
    
    def puede_registrar_transferencias(self):
        """Admin y bodega pueden registrar transferencias"""
        return self.es_admin() or self.es_bodega()
    
    def puede_embalar(self):
        """Admin y despacho pueden embalar"""
        return self.es_admin() or self.es_despacho()
    
    def puede_emitir_guias(self):
        """Solo admin puede emitir guías SAP"""
        return self.es_admin()
    
    def nombre_corto(self):
        """Retorna el primer nombre"""
        return self.nombre_completo.split()[0] if self.nombre_completo else self.username
    
    def puede_gestionar_bodega(self, codigo_bodega):
        """
        Verifica si el usuario puede gestionar una bodega específica.
        Admin puede gestionar todas.
        """
        if self.es_admin():
            return True
        return self.bodegas_asignadas.filter(codigo=codigo_bodega, activa=True).exists()
    
    def get_bodegas_codigos(self):
        """Retorna lista de códigos de bodegas asignadas"""
        if self.es_admin():
            return list(Bodega.objects.filter(activa=True).values_list('codigo', flat=True))
        return list(self.bodegas_asignadas.filter(activa=True).values_list('codigo', flat=True))
