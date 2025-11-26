from django.db import models
from django.conf import settings
from django.utils import timezone
import pytz


def get_chile_date():
    """Retorna la fecha actual en la zona horaria de Chile"""
    chile_tz = pytz.timezone('America/Santiago')
    return timezone.now().astimezone(chile_tz).date()


def get_chile_time():
    """Retorna la hora actual en la zona horaria de Chile"""
    chile_tz = pytz.timezone('America/Santiago')
    return timezone.now().astimezone(chile_tz).time()


class Solicitud(models.Model):
    """
    Modelo de Solicitud para Sistema PESCO
    Representa una solicitud de producto/material
    """
    
    TIPOS = [
        ('PC', 'PC'),
        ('OC', 'OC'),
        ('EM', 'Emergencia'),
        ('ST', 'Solicitud de Traslado'),
        ('OF', 'Oficina'),
        ('RM', 'Retiro de Mercancías'),
    ]
    
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('en_despacho', 'En Despacho'),
        ('embalado', 'Embalado'),
        ('despachado', 'Despachado'),
        ('cancelado', 'Cancelado'),
    ]
    
    TRANSPORTES = [
        ('PESCO', 'Camión PESCO'),
        ('VARMONTT', 'Varmontt'),
        ('STARKEN', 'Starken'),
        ('KAIZEN', 'Kaizen'),
        ('RETIRA_CLIENTE', 'Retira cliente'),
        ('OTRO', 'Otro / Coordinado'),
    ]

    # Información básica
    fecha_solicitud = models.DateField(
        default=get_chile_date,
        verbose_name='Fecha de solicitud',
        db_index=True
    )
    hora_solicitud = models.TimeField(
        default=get_chile_time,
        verbose_name='Hora de solicitud'
    )
    tipo = models.CharField(
        max_length=2, 
        choices=TIPOS,
        verbose_name='Tipo de solicitud'
    )
    numero_pedido = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de pedido / OF'
    )
    numero_st = models.CharField(
        max_length=20,
        blank=True,
        editable=False,
        verbose_name='Número ST automático'
    )
    cliente = models.CharField(
        max_length=200,
        verbose_name='Cliente',
        db_index=True
    )
    
    # Producto
    codigo = models.CharField(
        max_length=50,
        verbose_name='Código de producto',
        db_index=True
    )
    descripcion = models.TextField(
        verbose_name='Descripción del producto'
    )
    cantidad_solicitada = models.IntegerField(
        verbose_name='Cantidad solicitada'
    )
    
    # Ubicación y observaciones
    bodega = models.CharField(
        max_length=50,
        blank=True,  # puede quedar en blanco; el admin o la IA la definirán después
        verbose_name='Bodega origen'
    )
    transporte = models.CharField(
        max_length=20,
        choices=TRANSPORTES,
        default='PESCO',
        verbose_name='Transporte'
    )
    observacion = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    # Estado y prioridad
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='pendiente',
        verbose_name='Estado',
        db_index=True
    )
    urgente = models.BooleanField(
        default=False,
        verbose_name='¿Es urgente?',
        db_index=True
    )
    
    # Relaciones
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_creadas',
        verbose_name='Solicitante'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado el'
    )
    
    class Meta:
        db_table = 'solicitudes'
        ordering = ['-fecha_solicitud', '-hora_solicitud']
        verbose_name = 'Solicitud'
        verbose_name_plural = 'Solicitudes'
        indexes = [
            # Índice principal para filtros por estado (usado en TODOS los roles)
            models.Index(fields=['estado'], name='idx_estado'),
            
            # Índice compuesto para filtros de bodega/despacho (estado + id para ordenamiento)
            models.Index(fields=['estado', 'id'], name='idx_estado_id'),
            
            # Índice para búsquedas por cliente (muy común)
            models.Index(fields=['cliente'], name='idx_cliente'),
            
            # Índice para búsquedas por código de producto
            models.Index(fields=['codigo'], name='idx_codigo'),
            
            # Índice para búsquedas por número de pedido
            models.Index(fields=['numero_pedido'], name='idx_numero_pedido'),
            
            # Índice para búsquedas por número ST
            models.Index(fields=['numero_st'], name='idx_numero_st'),
            
            # Índice para filtros por tipo
            models.Index(fields=['tipo'], name='idx_tipo'),
            
            # Índice compuesto para filtros combinados (estado + tipo)
            models.Index(fields=['estado', 'tipo'], name='idx_estado_tipo'),
            
            # Índice para solicitudes urgentes
            models.Index(fields=['urgente', 'estado'], name='idx_urgente_estado'),
            
            # Índice para ordenamiento por fecha (reportes y KPIs)
            models.Index(fields=['-fecha_solicitud', '-hora_solicitud'], name='idx_fecha_hora'),
            
            # Índice para generación de números ST (tipo + numero_st)
            models.Index(fields=['tipo', 'numero_st'], name='idx_tipo_st'),
            
            # Índice para relación con solicitante (JOIN optimization)
            models.Index(fields=['solicitante'], name='idx_solicitante'),
        ]
    
    def __str__(self):
        return f"Solicitud #{self.id} - {self.cliente} - {self.get_estado_display()}"
    
    def dias_desde_solicitud(self):
        """Calcula los días transcurridos desde la solicitud"""
        chile_tz = pytz.timezone('America/Santiago')
        hoy_chile = timezone.now().astimezone(chile_tz).date()
        return (hoy_chile - self.fecha_solicitud).days
    
    def es_urgente_pendiente(self):
        """Retorna True si es urgente y está pendiente"""
        return self.urgente and self.estado in ['pendiente', 'en_despacho']
    
    def puede_pasar_a_despacho(self):
        """Verifica si puede cambiar a estado en_despacho"""
        return self.estado == 'pendiente'
    
    def puede_embalar(self):
        """Verifica si puede cambiar a estado embalado"""
        return self.estado == 'en_despacho'
    
    def puede_despachar(self):
        """Verifica si puede cambiar a estado despachado"""
        return self.estado == 'embalado'
    
    def color_estado(self):
        """Retorna el color CSS según el estado"""
        colores = {
            'pendiente': 'warning',
            'en_despacho': 'info',
            'embalado': 'success',
            'despachado': 'primary',
            'cancelado': 'danger',
        }
        return colores.get(self.estado, 'secondary')
    
    def icono_estado(self):
        """Retorna el icono Bootstrap según el estado"""
        iconos = {
            'pendiente': 'clock',
            'en_despacho': 'truck',
            'embalado': 'box-seam',
            'despachado': 'check-circle',
            'cancelado': 'x-circle',
        }
        return iconos.get(self.estado, 'circle')

    def save(self, *args, **kwargs):
        """
        Genera automáticamente el número ST cuando corresponde.
        Reinicia la numeración cada año.
        """
        if self.tipo == 'ST' and not self.numero_st:
            self.numero_st = self._generar_numero_st()
        super().save(*args, **kwargs)

    def _generar_numero_st(self):
        chile_tz = pytz.timezone('America/Santiago')
        year = timezone.now().astimezone(chile_tz).year
        prefix = f"ST-{year}-"
        ultimo = (
            Solicitud.objects
            .filter(tipo='ST', numero_st__startswith=prefix)
            .order_by('-numero_st')
            .first()
        )
        if ultimo and ultimo.numero_st:
            try:
                correlativo = int(ultimo.numero_st.split('-')[-1]) + 1
            except ValueError:
                correlativo = 1
        else:
            correlativo = 1
        return f"{prefix}{correlativo:03d}"

    def total_codigos(self):
        """
        Retorna la cantidad de códigos asociados a la solicitud.
        - Para solicitudes nuevas: cantidad de filas en SolicitudDetalle.
        - Para solicitudes antiguas sin detalles: al menos 1 si existe código en cabecera.
        """
        count = self.detalles.count()
        if count == 0 and self.codigo:
            return 1
        return count


class SolicitudDetalle(models.Model):
    """
    Líneas de producto asociadas a una solicitud.
    Permite múltiples códigos por solicitud.
    """

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Solicitud',
    )
    codigo = models.CharField(
        max_length=50,
        verbose_name='Código de producto',
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
    )
    cantidad = models.PositiveIntegerField(
        verbose_name='Cantidad',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado el',
    )

    class Meta:
        db_table = 'solicitudes_detalle'
        verbose_name = 'Detalle de solicitud'
        verbose_name_plural = 'Detalles de solicitud'
        ordering = ['id']
        indexes = [
            # Índice para JOIN con solicitudes (usado en TODAS las consultas)
            models.Index(fields=['solicitud'], name='idx_detalle_solicitud'),
            
            # Índice compuesto para búsquedas por solicitud + código
            models.Index(fields=['solicitud', 'codigo'], name='idx_detalle_sol_codigo'),
            
            # Índice para búsquedas por código de producto
            models.Index(fields=['codigo'], name='idx_detalle_codigo'),
        ]

    def __str__(self):
        return f"{self.codigo} x {self.cantidad} (Solicitud #{self.solicitud_id})"
