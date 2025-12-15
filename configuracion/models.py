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


class TipoSolicitud(models.Model):
    """
    Configuración de tipos de solicitud (PC, OC, EM, ST, OF, RM, etc.)
    Permite gestionar los tipos de solicitud desde la base de datos.
    """
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    icono = models.CharField(max_length=50, default='file-text', blank=True, verbose_name='Icono')
    color = models.CharField(max_length=30, default='primary', blank=True, verbose_name='Color')

    # Caché en memoria para evitar queries repetidas
    _cache_objetos = {}
    _cache_etiquetas = {}
    _cache_cargado = False

    class Meta:
        db_table = 'config_tipos_solicitud'
        ordering = ['orden', 'codigo']
        verbose_name = 'Tipo de solicitud'
        verbose_name_plural = 'Tipos de solicitud'

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    @classmethod
    def _cargar_cache(cls):
        """Carga todos los tipos en caché una sola vez"""
        if cls._cache_cargado:
            return
        
        tipos = cls.objects.all()
        for tipo in tipos:
            cls._cache_objetos[tipo.codigo] = tipo
            cls._cache_etiquetas[tipo.codigo] = tipo.nombre
        
        cls._cache_cargado = True

    @classmethod
    def activos(cls):
        """Retorna tipos activos"""
        cls._cargar_cache()
        return cls.objects.filter(activo=True).order_by('orden', 'codigo')

    @classmethod
    def obtener(cls, codigo):
        """Obtiene un tipo usando caché en memoria"""
        cls._cargar_cache()
        return cls._cache_objetos.get(codigo)

    @classmethod
    def etiqueta(cls, codigo):
        """Retorna la etiqueta usando caché"""
        cls._cargar_cache()
        if codigo in cls._cache_etiquetas:
            return cls._cache_etiquetas[codigo]
        return codigo
    
    @classmethod
    def limpiar_cache(cls):
        """Limpia el caché (útil para testing o después de cambios)"""
        cls._cache_objetos.clear()
        cls._cache_etiquetas.clear()
        cls._cache_cargado = False
