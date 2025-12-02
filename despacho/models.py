from django.conf import settings
from django.db import models
from django.utils import timezone

from solicitudes.models import Solicitud
from configuracion.models import EstadoWorkflow, TransporteConfig


class Bulto(models.Model):
    """
    Representa un bulto físico (caja/pallet) que agrupa múltiples solicitudes.
    """

    TIPOS = [
        ('caja', 'Caja'),
        ('pallet', 'Pallet'),
        ('otro', 'Otro'),
    ]

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    estado = models.CharField(max_length=30, default='pendiente')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='caja')
    transportista = models.CharField(
        max_length=50,
        default='PESCO'
    )
    transportista_extra = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Transportista externo'
    )
    numero_guia_transportista = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='N° guía transportista'
    )
    peso_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    largo_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    ancho_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    alto_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_embalaje = models.DateTimeField(null=True, blank=True, verbose_name='Fecha embalaje')
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='bultos_creados'
    )
    solicitudes = models.ManyToManyField(
        Solicitud,
        through='BultoSolicitud',
        related_name='bultos'
    )

    class Meta:
        db_table = 'despacho_bultos'
        ordering = ['-fecha_creacion']
        verbose_name = 'Bulto'
        verbose_name_plural = 'Bultos'

    def __str__(self):
        return self.codigo

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = self._generar_codigo()
        super().save(*args, **kwargs)

    def _generar_codigo(self):
        año = timezone.now().year
        prefix = f"BUL-{año}-"
        ultimo = Bulto.objects.filter(codigo__startswith=prefix).order_by('-codigo').first()
        if ultimo:
            try:
                correlativo = int(ultimo.codigo.split('-')[-1]) + 1
            except (ValueError, IndexError):
                correlativo = 1
        else:
            correlativo = 1
        return f"{prefix}{correlativo:04d}"

    @property
    def volumen_m3(self):
        return float(self.largo_cm or 0) * float(self.ancho_cm or 0) * float(self.alto_cm or 0) / 1_000_000

    def es_transporte_propio(self):
        config = TransporteConfig.obtener(self.transportista)
        if config:
            return config.es_propio
        return self.transportista == 'PESCO'

    def get_estado_display(self):
        return EstadoWorkflow.etiqueta(EstadoWorkflow.TIPO_BULTO, self.estado)

    def color_estado(self):
        return EstadoWorkflow.color_para(EstadoWorkflow.TIPO_BULTO, self.estado)

    def get_transportista_display(self):
        return TransporteConfig.etiqueta(self.transportista)


class BultoSolicitud(models.Model):
    """
    Vincula un bulto con una solicitud.
    """

    bulto = models.ForeignKey(Bulto, on_delete=models.CASCADE, related_name='relaciones')
    solicitud = models.ForeignKey(Solicitud, on_delete=models.CASCADE, related_name='relaciones_bulto')
    comentario = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'despacho_bulto_solicitudes'
        ordering = ['id']

    def __str__(self):
        return f"{self.bulto.codigo} → Solicitud #{self.solicitud_id}"
