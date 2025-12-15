from django.db import models
from django.conf import settings
from django.utils import timezone
import pytz

from configuracion.models import EstadoWorkflow, TransporteConfig, TipoSolicitud


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
        max_length=10,  # Aumentado para permitir códigos más largos
        choices=TIPOS,  # Se mantiene como fallback si no hay tipos en BD
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
    numero_ot = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número OT',
        help_text='Orden de transporte asignada por el transportista externo'
    )
    numero_guia_despacho = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Número de Guía/Factura',
        help_text='Número de guía o factura que confirma el despacho'
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
        max_length=50,
        default='PESCO',
        verbose_name='Transporte'
    )
    observacion = models.TextField(
        blank=True,
        verbose_name='Observaciones'
    )
    
    # Estado y prioridad
    estado = models.CharField(
        max_length=50,
        default='pendiente',
        verbose_name='Estado',
        db_index=True
    )
    urgente = models.BooleanField(
        default=False,
        verbose_name='¿Es urgente?',
        db_index=True
    )
    afecta_stock = models.BooleanField(
        default=True,
        verbose_name='¿Afecta stock?',
        help_text='Si es False, no se descuenta stock (órdenes especiales, traslados, etc.)'
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
            models.Index(fields=['numero_ot'], name='idx_numero_ot'),
            
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
    
    def estado_config(self):
        return EstadoWorkflow.obtener(EstadoWorkflow.TIPO_SOLICITUD, self.estado)

    def get_estado_display(self):
        return EstadoWorkflow.etiqueta(EstadoWorkflow.TIPO_SOLICITUD, self.estado)

    def get_tipo_display(self):
        """Retorna el nombre del tipo desde TipoSolicitud si existe, sino retorna el código"""
        if self.tipo:
            nombre = TipoSolicitud.etiqueta(self.tipo)
            # Si no está en caché, retornar el código como fallback
            if nombre == self.tipo:
                # Intentar obtener desde el modelo directamente
                tipo_obj = TipoSolicitud.obtener(self.tipo)
                if tipo_obj:
                    return tipo_obj.nombre
                # Fallback a choices hardcodeados si no existe en BD
                for codigo, nombre_choice in self.TIPOS:
                    if codigo == self.tipo:
                        return nombre_choice
            return nombre
        return self.tipo or ''

    def color_estado(self):
        """Retorna el color CSS según el estado"""
        return EstadoWorkflow.color_para(EstadoWorkflow.TIPO_SOLICITUD, self.estado)
    
    def icono_estado(self):
        """Retorna el icono Bootstrap según el estado"""
        return EstadoWorkflow.icono_para(EstadoWorkflow.TIPO_SOLICITUD, self.estado)

    def transporte_config(self):
        return TransporteConfig.obtener(self.transporte)

    def get_transporte_display(self):
        return TransporteConfig.etiqueta(self.transporte)

    def transporte_requiere_ot(self):
        config = self.transporte_config()
        return config.requiere_ot if config else False

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
    
    # Bodega y estado por producto
    bodega = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Bodega',
        help_text='Bodega donde se encuentra este producto',
        db_index=True
    )
    estado_bodega = models.CharField(
        max_length=30,
        default='pendiente',
        verbose_name='Estado en bodega',
        db_index=True
    )
    bulto = models.ForeignKey(
        'despacho.Bulto',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detalles',
        verbose_name='Bulto asignado'
    )
    preparado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_preparados',
        verbose_name='Preparado por'
    )
    fecha_preparacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de preparaci\u00f3n'
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
            
            # NUEVOS: Índices para bodegas
            models.Index(fields=['bodega'], name='idx_detalle_bodega'),
            models.Index(fields=['estado_bodega'], name='idx_detalle_estado_bod'),
            models.Index(fields=['bodega', 'estado_bodega'], name='idx_detalle_bod_estado'),
        ]

    def __str__(self):
        return f"{self.codigo} x {self.cantidad} (Solicitud #{self.solicitud_id})"

    def estado_bodega_config(self):
        return EstadoWorkflow.obtener(EstadoWorkflow.TIPO_DETALLE, self.estado_bodega)

    def get_estado_bodega_display(self):
        return EstadoWorkflow.etiqueta(EstadoWorkflow.TIPO_DETALLE, self.estado_bodega)
