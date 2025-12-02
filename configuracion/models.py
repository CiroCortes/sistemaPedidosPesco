from django.db import models


class EstadoWorkflow(models.Model):
    TIPO_SOLICITUD = 'solicitud'
    TIPO_DETALLE = 'detalle'
    TIPO_BULTO = 'bulto'

    TIPOS = [
        (TIPO_SOLICITUD, 'Solicitudes'),
        (TIPO_DETALLE, 'Detalle de bodega'),
        (TIPO_BULTO, 'Bultos'),
    ]

    slug = models.SlugField(max_length=50)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    orden = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=30, default='secondary')
    icono = models.CharField(max_length=50, default='circle')
    activo = models.BooleanField(default=True)
    es_terminal = models.BooleanField(default=False)

    class Meta:
        db_table = 'config_estados'
        ordering = ['tipo', 'orden']
        unique_together = ('tipo', 'slug')
        verbose_name = 'Estado configurable'
        verbose_name_plural = 'Estados configurables'

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

    @classmethod
    def activos_para(cls, tipo):
        return cls.objects.filter(tipo=tipo, activo=True).order_by('orden')

    @classmethod
    def obtener(cls, tipo, slug):
        return cls.objects.filter(tipo=tipo, slug=slug).first()

    @classmethod
    def etiqueta(cls, tipo, slug):
        estado = cls.obtener(tipo, slug)
        if estado:
            return estado.nombre
        return slug.replace('_', ' ').title()

    @classmethod
    def color_para(cls, tipo, slug):
        estado = cls.obtener(tipo, slug)
        return estado.color if estado else 'secondary'

    @classmethod
    def icono_para(cls, tipo, slug):
        estado = cls.obtener(tipo, slug)
        return estado.icono if estado else 'circle'


class TransporteConfig(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    es_propio = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    requiere_ot = models.BooleanField(default=False)

    class Meta:
        db_table = 'config_transportes'
        ordering = ['orden', 'nombre']
        verbose_name = 'Transporte configurable'
        verbose_name_plural = 'Transportes configurables'

    def __str__(self):
        return self.nombre

    @classmethod
    def activos(cls):
        return cls.objects.filter(activo=True).order_by('orden', 'nombre')

    @classmethod
    def obtener(cls, slug):
        return cls.objects.filter(slug=slug).first()

    @classmethod
    def etiqueta(cls, slug):
        transporte = cls.obtener(slug)
        return transporte.nombre if transporte else slug.replace('_', ' ').title()

