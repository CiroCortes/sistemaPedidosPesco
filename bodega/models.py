from django.db import models
from django.utils import timezone

from core.models import Usuario
from solicitudes.models import Solicitud, SolicitudDetalle


def get_local_date():
    return timezone.localdate()


def get_local_time():
    return timezone.localtime().time()

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


class StockReserva(models.Model):
    """
    Reserva de stock asociada a un detalle de solicitud.
    Permite comprometer unidades para evitar duplicidades.
    """
    ESTADOS = [
        ('reservada', 'Reservada'),
        ('consumida', 'Consumida'),
        ('liberada', 'Liberada'),
    ]

    detalle = models.OneToOneField(
        SolicitudDetalle,
        on_delete=models.CASCADE,
        related_name='reserva'
    )
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='reservas'
    )
    codigo = models.CharField(max_length=50, db_index=True)
    bodega = models.CharField(max_length=50, db_index=True)
    cantidad = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='reservada')
    observacion = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bodega_stock_reservas'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['codigo', 'bodega']),
            models.Index(fields=['estado']),
        ]

    def __str__(self):
        return f"Reserva {self.codigo} ({self.cantidad}) - {self.get_estado_display()}"

    def marcar_consumida(self):
        self.estado = 'consumida'
        self.save(update_fields=['estado', 'updated_at'])

    def liberar(self):
        self.estado = 'liberada'
        self.save(update_fields=['estado', 'updated_at'])


class BodegaTransferencia(models.Model):
    """
    Registro de transferencias realizadas por bodega hacia despacho.
    """
    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='transferencias'
    )
    detalle = models.ForeignKey(
        SolicitudDetalle,
        on_delete=models.CASCADE,
        related_name='transferencias'
    )
    reserva = models.ForeignKey(
        StockReserva,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferencias'
    )
    numero_transferencia = models.CharField(max_length=50)
    fecha_transferencia = models.DateField(default=get_local_date)
    hora_transferencia = models.TimeField(default=get_local_time)
    bodega_origen = models.CharField(max_length=50)
    bodega_destino = models.CharField(max_length=50, default='013')
    cantidad = models.PositiveIntegerField()
    registrado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        related_name='transferencias_registradas'
    )
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bodega_transferencias'
        ordering = ['-fecha_transferencia', '-hora_transferencia']
        indexes = [
            models.Index(fields=['numero_transferencia']),
            models.Index(fields=['fecha_transferencia', 'hora_transferencia']),
            models.Index(fields=['bodega_origen']),
        ]

    def __str__(self):
        return f"Transferencia {self.numero_transferencia} - {self.detalle.codigo}"
