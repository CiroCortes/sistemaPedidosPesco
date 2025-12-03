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

    # Caché en memoria para evitar queries repetidas
    _cache_objetos = {}
    _cache_etiquetas = {}
    _cache_colores = {}
    _cache_iconos = {}
    _cache_cargado = False

    class Meta:
        db_table = 'config_estados'
        ordering = ['tipo', 'orden']
        unique_together = ('tipo', 'slug')
        verbose_name = 'Estado configurable'
        verbose_name_plural = 'Estados configurables'

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"

    @classmethod
    def _cargar_cache(cls):
        """Carga todos los estados en caché una sola vez"""
        if cls._cache_cargado:
            return
        
        estados = cls.objects.all()
        for estado in estados:
            key = (estado.tipo, estado.slug)
            cls._cache_objetos[key] = estado
            cls._cache_etiquetas[key] = estado.nombre
            cls._cache_colores[key] = estado.color
            cls._cache_iconos[key] = estado.icono
        
        cls._cache_cargado = True

    @classmethod
    def activos_para(cls, tipo):
        """Retorna estados activos usando caché"""
        cls._cargar_cache()
        # Filtrar del caché en lugar de hacer query
        estados_activos = [
            estado for key, estado in cls._cache_objetos.items()
            if key[0] == tipo and estado.activo
        ]
        return sorted(estados_activos, key=lambda x: x.orden)

    @classmethod
    def obtener(cls, tipo, slug):
        """Obtiene un estado usando caché en memoria"""
        cls._cargar_cache()
        key = (tipo, slug)
        return cls._cache_objetos.get(key)

    @classmethod
    def etiqueta(cls, tipo, slug):
        """Retorna la etiqueta usando caché"""
        cls._cargar_cache()
        key = (tipo, slug)
        if key in cls._cache_etiquetas:
            return cls._cache_etiquetas[key]
        return slug.replace('_', ' ').title()

    @classmethod
    def color_para(cls, tipo, slug):
        """Retorna el color usando caché"""
        cls._cargar_cache()
        key = (tipo, slug)
        return cls._cache_colores.get(key, 'secondary')

    @classmethod
    def icono_para(cls, tipo, slug):
        """Retorna el icono usando caché"""
        cls._cargar_cache()
        key = (tipo, slug)
        return cls._cache_iconos.get(key, 'circle')
    
    @classmethod
    def limpiar_cache(cls):
        """Limpia el caché (útil para testing o después de cambios)"""
        cls._cache_objetos.clear()
        cls._cache_etiquetas.clear()
        cls._cache_colores.clear()
        cls._cache_iconos.clear()
        cls._cache_cargado = False


class TransporteConfig(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    es_propio = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    requiere_ot = models.BooleanField(default=False)

    # Caché en memoria para evitar queries repetidas
    _cache_objetos = {}
    _cache_etiquetas = {}
    _cache_cargado = False

    class Meta:
        db_table = 'config_transportes'
        ordering = ['orden', 'nombre']
        verbose_name = 'Transporte configurable'
        verbose_name_plural = 'Transportes configurables'

    def __str__(self):
        return self.nombre

    @classmethod
    def _cargar_cache(cls):
        """Carga todos los transportes en caché una sola vez"""
        if cls._cache_cargado:
            return
        
        transportes = cls.objects.all()
        for transporte in transportes:
            cls._cache_objetos[transporte.slug] = transporte
            cls._cache_etiquetas[transporte.slug] = transporte.nombre
        
        cls._cache_cargado = True

    @classmethod
    def activos(cls):
        return cls.objects.filter(activo=True).order_by('orden', 'nombre')

    @classmethod
    def obtener(cls, slug):
        """Obtiene un transporte usando caché en memoria"""
        cls._cargar_cache()
        return cls._cache_objetos.get(slug)

    @classmethod
    def etiqueta(cls, slug):
        """Retorna la etiqueta usando caché"""
        cls._cargar_cache()
        if slug in cls._cache_etiquetas:
            return cls._cache_etiquetas[slug]
        return slug.replace('_', ' ').title()
    
    @classmethod
    def limpiar_cache(cls):
        """Limpia el caché (útil para testing o después de cambios)"""
        cls._cache_objetos.clear()
        cls._cache_etiquetas.clear()
        cls._cache_cargado = False

