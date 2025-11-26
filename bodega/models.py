from django.db import models
from core.models import Usuario

class Stock(models.Model):
    """
    Modelo que mapea la tabla 'stock' en Supabase.
    Almacena el inventario de productos por bodega.
    """
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    cod_grupo = models.IntegerField(blank=True, null=True)
    descripcion_grupo = models.CharField(max_length=200, blank=True, null=True)
    bodega = models.CharField(max_length=20)
    bodega_nombre = models.CharField(max_length=200, blank=True, null=True)
    ubicacion = models.CharField(max_length=100, blank=True, null=True)
    ubicacion_2 = models.CharField(max_length=100, blank=True, null=True)
    stock_disponible = models.IntegerField(default=0)
    stock_reservado = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    total = models.DecimalField(max_digits=15, decimal_places=3, blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False  # Tabla creada manualmente en Supabase
        db_table = 'stock'
        unique_together = [['codigo', 'bodega']]
        ordering = ['codigo', 'bodega']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['bodega']),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.bodega} ({self.stock_real})"

    @property
    def stock_real(self):
        """Calcula el stock real disponible para uso (físico - reservado)"""
        return max(0, self.stock_disponible - self.stock_reservado)

    @property
    def estado_stock(self):
        """Retorna el estado del stock para UI"""
        real = self.stock_real
        if real <= 0:
            return 'sin_stock'
        elif real <= 5:
            return 'stock_bajo'
        return 'disponible'


class CargaStock(models.Model):
    """
    Historial de cargas de archivos de stock.
    """
    ESTADOS = [
        ('procesando', 'Procesando'),
        ('activo', 'Activo'),
        ('expirado', 'Expirado'),
        ('error', 'Error'),
    ]

    fecha_carga = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        db_column='usuario_id',
        related_name='cargas_stock'
    )
    nombre_archivo = models.CharField(max_length=255)
    total_productos = models.IntegerField(default=0)
    total_bodegas = models.IntegerField(default=0)
    archivo_url = models.URLField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='procesando')
    mensaje_error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False  # Tabla creada manualmente en Supabase
        db_table = 'carga_stock'
        ordering = ['-fecha_carga']

    def __str__(self):
        return f"Carga {self.id} - {self.fecha_carga.strftime('%d/%m/%Y')}"
