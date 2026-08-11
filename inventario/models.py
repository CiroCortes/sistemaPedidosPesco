from django.db import models
from django.conf import settings


class StockSAP(models.Model):
    """
    Espejo de la tabla de stock existente en Supabase
    Tabla: 'stock'
    """
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=50, db_index=True)
    descripcion = models.TextField(null=True, blank=True)
    cod_grupo = models.IntegerField(null=True, blank=True)
    descripcion_grupo = models.CharField(max_length=200, null=True, blank=True)
    bodega = models.CharField(max_length=20, db_index=True)
    bodega_nombre = models.CharField(max_length=200, null=True, blank=True)
    ubicacion = models.CharField(max_length=100, null=True, blank=True)
    ubicacion_2 = models.CharField(max_length=100, null=True, blank=True)
    stock_disponible = models.IntegerField(default=0)
    stock_reservado = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    categoria = models.CharField(max_length=100, null=True, blank=True)
    ultima_actualizacion = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        managed = False  # Ya existe en BD
        db_table = 'stock'
        verbose_name = 'Stock SAP'
        verbose_name_plural = 'Stock SAP'
        ordering = ['codigo', 'bodega']
    
    def __str__(self):
        return f"{self.codigo} - {self.bodega} (Stock: {self.stock_disponible})"


class CargaStock(models.Model):
    """
    Registro de cargas existente
    Tabla: 'carga_stock'
    """
    id = models.BigAutoField(primary_key=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    usuario_id = models.IntegerField(null=True, blank=True)  # ID de usuario numérico
    nombre_archivo = models.CharField(max_length=255, null=True, blank=True)
    total_productos = models.IntegerField(null=True, blank=True)
    total_bodegas = models.IntegerField(null=True, blank=True)
    archivo_url = models.TextField(null=True, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=[
            ('procesando', 'Procesando'),
            ('completado', 'Completado'),
            ('error', 'Error'),
        ],
        default='procesando'
    )
    mensaje_error = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        managed = False  # Ya existe en BD
        db_table = 'carga_stock'
        ordering = ['-fecha_carga']
        verbose_name = 'Carga de Stock'
        verbose_name_plural = 'Cargas de Stock'
    
    def __str__(self):
        return f"Carga {self.id} - {self.fecha_carga} ({self.estado})"
