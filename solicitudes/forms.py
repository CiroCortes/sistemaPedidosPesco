from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone
import pytz

from core.models import Bodega
from configuracion.models import TransporteConfig, EstadoWorkflow, TipoSolicitud
from .models import Solicitud, SolicitudDetalle
from despacho.models import Bulto

class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = [
            'tipo', 
            'numero_pedido', 
            'numero_ot',
            'cliente', 
            'transporte', 
            'observacion', 
            'urgente',
            'afecta_stock'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'numero_pedido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 25111045'}),
            'numero_ot': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número OT de transporte'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del cliente o sucursal'}),
            'transporte': forms.Select(attrs={'class': 'form-select'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'urgente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'afecta_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_transportes()
        self._load_tipos()

    def _load_transportes(self):
        choices = [(t.slug, t.nombre) for t in TransporteConfig.activos()]
        if not choices:
            choices = [('PESCO', 'Camión PESCO')]
        self.fields['transporte'].choices = choices

    def _load_tipos(self):
        """Carga tipos de solicitud desde la base de datos"""
        tipos = TipoSolicitud.activos()
        if tipos.exists():
            choices = [(t.codigo, t.nombre) for t in tipos]
        else:
            # Fallback a choices hardcodeados si no hay tipos en BD
            choices = Solicitud.TIPOS
        self.fields['tipo'].choices = choices

class SolicitudDetalleForm(forms.ModelForm):
    bodega = forms.ChoiceField(
        label='Bodega',
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = SolicitudDetalle
        fields = ['codigo', 'descripcion', 'cantidad', 'bodega']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
    
    def __init__(self, *args, available_bodegas=None, default_bodega=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = available_bodegas or list(
            Bodega.objects.filter(activa=True).order_by('codigo').values_list('codigo', 'nombre')
        )
        
        choices = [('', 'Selecciona bodega')] + [
            (codigo, f"{codigo} · {nombre}") for codigo, nombre in queryset
        ]
        self.fields['bodega'].choices = choices
        
        # Si el detalle ya tiene una bodega (ej. edición) que no esté activa, mantenerla visible
        current_value = self.initial.get('bodega')
        if current_value and not any(current_value == c for c, _ in choices):
            self.fields['bodega'].choices.append((current_value, f"{current_value} · (inactiva)"))
        
        if default_bodega and not self.initial.get('bodega'):
            self.initial['bodega'] = default_bodega

SolicitudDetalleFormSet = inlineformset_factory(
    Solicitud,
    SolicitudDetalle,
    form=SolicitudDetalleForm,
    extra=1,  # Iniciar con solo 1 línea
    max_num=45,
    can_delete=True,
)

class SolicitudEdicionAdminForm(forms.ModelForm):
    """Formulario para edición de solicitudes por parte del administrador"""
    class Meta:
        model = Solicitud
        fields = [
            'tipo', 
            'numero_pedido', 
            'numero_ot',
            'numero_guia_despacho',
            'cliente', 
            'transporte', 
            'estado',
            'urgente', 
            'afecta_stock',
            'observacion'
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'numero_pedido': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_ot': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_guia_despacho': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Número de guía o factura'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'transporte': forms.Select(attrs={'class': 'form-select'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'urgente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'afecta_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [(t.slug, t.nombre) for t in TransporteConfig.activos()]
        if not choices:
            choices = [('PESCO', 'Camión PESCO')]
        self.fields['transporte'].choices = choices
        
        # Cargar tipos de solicitud
        tipos = TipoSolicitud.activos()
        if tipos.exists():
            tipo_choices = [(t.codigo, t.nombre) for t in tipos]
        else:
            tipo_choices = Solicitud.TIPOS
        self.fields['tipo'].choices = tipo_choices
        
        estados = [(e.slug, e.nombre) for e in EstadoWorkflow.activos_para(EstadoWorkflow.TIPO_SOLICITUD)]
        if estados:
            self.fields['estado'].choices = estados


class SolicitudDetalleEdicionAdminForm(forms.ModelForm):
    """
    Formulario extendido para que el admin pueda editar fechas de preparación
    y corregir errores en los horarios que afectan los KPIs.
    """
    fecha_preparacion = forms.DateTimeField(
        required=False,
        label='Fecha/Hora de Preparación',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text='Ajusta la fecha y hora si hubo error en el registro'
    )
    
    bodega = forms.ChoiceField(
        label='Bodega',
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    estado_bodega = forms.ChoiceField(
        label='Estado en Bodega',
        required=False,
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = SolicitudDetalle
        fields = ['codigo', 'descripcion', 'cantidad', 'bodega', 'estado_bodega', 'fecha_preparacion']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar bodegas activas
        queryset = list(
            Bodega.objects.filter(activa=True).order_by('codigo').values_list('codigo', 'nombre')
        )
        choices = [('', 'Selecciona bodega')] + [
            (codigo, f"{codigo} · {nombre}") for codigo, nombre in queryset
        ]
        self.fields['bodega'].choices = choices
        
        # Cargar estados de bodega
        estados = [(e.slug, e.nombre) for e in EstadoWorkflow.activos_para(EstadoWorkflow.TIPO_DETALLE)]
        if not estados:
            estados = [
                ('pendiente', 'Pendiente'),
                ('preparado', 'Preparado'),
                ('despachado', 'Despachado'),
            ]
        self.fields['estado_bodega'].choices = estados
        
        # Convertir fecha_preparacion a formato datetime-local si existe
        if self.instance and self.instance.fecha_preparacion:
            # Convertir a zona horaria de Chile antes de mostrar
            chile_tz = pytz.timezone('America/Santiago')
            fecha_chile = self.instance.fecha_preparacion.astimezone(chile_tz)
            # Formato: YYYY-MM-DDTHH:MM
            fecha_str = fecha_chile.strftime('%Y-%m-%dT%H:%M')
            self.initial['fecha_preparacion'] = fecha_str
    
    def clean_fecha_preparacion(self):
        """
        Convertir fecha naive del navegador a aware con zona horaria de Chile.
        Usa make_aware() que detecta automáticamente horario de verano/invierno.
        """
        fecha = self.cleaned_data.get('fecha_preparacion')
        if fecha:
            # Si la fecha es naive (sin zona horaria), asumimos que está en hora de Chile
            if timezone.is_naive(fecha):
                chile_tz = pytz.timezone('America/Santiago')
                # make_aware() detecta automáticamente el DST correcto para la fecha
                fecha = timezone.make_aware(fecha, chile_tz)
            return fecha
        return None


SolicitudDetalleEdicionFormSet = inlineformset_factory(
    Solicitud,
    SolicitudDetalle,
    form=SolicitudDetalleEdicionAdminForm,
    extra=0,  # No mostrar líneas extras (usar botón "Agregar línea")
    can_delete=True,  # Permitir eliminar detalles
    max_num=45,  # Máximo 45 productos
)


class BultoEdicionAdminForm(forms.ModelForm):
    """
    Formulario para que el admin pueda editar fechas de embalaje, envío y entrega de bultos.
    Permite corregir errores en los horarios que afectan los KPIs.
    """
    estado = forms.ChoiceField(
        required=False,
        label='Estado',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    fecha_embalaje = forms.DateTimeField(
        required=False,
        label='Fecha/Hora de Embalaje',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text='Fecha y hora cuando se embaló el bulto'
    )
    
    fecha_envio = forms.DateTimeField(
        required=False,
        label='Fecha/Hora de Envío',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text='Fecha y hora cuando se envió el bulto'
    )
    
    fecha_entrega = forms.DateTimeField(
        required=False,
        label='Fecha/Hora de Entrega',
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local',
        }),
        help_text='Fecha y hora cuando se entregó el bulto'
    )
    
    class Meta:
        model = Bulto
        fields = ['fecha_embalaje', 'fecha_envio', 'fecha_entrega']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Cargar estados de bulto
        estados = [(e.slug, e.nombre) for e in EstadoWorkflow.activos_para(EstadoWorkflow.TIPO_BULTO)]
        if not estados:
            estados = [
                ('pendiente', 'Pendiente'),
                ('embalado', 'Embalado'),
                ('en_ruta', 'En Ruta'),
                ('entregado', 'Entregado'),
            ]
        self.fields['estado'].choices = estados
        
        # Establecer el estado actual del bulto como inicial
        if self.instance and self.instance.pk:
            self.initial['estado'] = self.instance.estado
        
        # Convertir fechas a formato datetime-local si existen (convertir a zona horaria de Chile)
        chile_tz = pytz.timezone('America/Santiago')
        if self.instance and self.instance.pk:
            if self.instance.fecha_embalaje:
                fecha_chile = self.instance.fecha_embalaje.astimezone(chile_tz)
                self.initial['fecha_embalaje'] = fecha_chile.strftime('%Y-%m-%dT%H:%M')
            if self.instance.fecha_envio:
                fecha_chile = self.instance.fecha_envio.astimezone(chile_tz)
                self.initial['fecha_envio'] = fecha_chile.strftime('%Y-%m-%dT%H:%M')
            if self.instance.fecha_entrega:
                fecha_chile = self.instance.fecha_entrega.astimezone(chile_tz)
                self.initial['fecha_entrega'] = fecha_chile.strftime('%Y-%m-%dT%H:%M')
    
    def clean_fecha_embalaje(self):
        """
        Convertir fecha naive del navegador a aware con zona horaria de Chile.
        Usa make_aware() que detecta automáticamente horario de verano/invierno.
        """
        fecha = self.cleaned_data.get('fecha_embalaje')
        if fecha:
            if timezone.is_naive(fecha):
                chile_tz = pytz.timezone('America/Santiago')
                # make_aware() detecta automáticamente el DST correcto para la fecha
                fecha = timezone.make_aware(fecha, chile_tz)
            return fecha
        return None
    
    def clean_fecha_envio(self):
        """
        Convertir fecha naive del navegador a aware con zona horaria de Chile.
        Usa make_aware() que detecta automáticamente horario de verano/invierno.
        """
        fecha = self.cleaned_data.get('fecha_envio')
        if fecha:
            if timezone.is_naive(fecha):
                chile_tz = pytz.timezone('America/Santiago')
                # make_aware() detecta automáticamente el DST correcto para la fecha
                fecha = timezone.make_aware(fecha, chile_tz)
            return fecha
        return None
    
    def clean_fecha_entrega(self):
        """
        Convertir fecha naive del navegador a aware con zona horaria de Chile.
        Usa make_aware() que detecta automáticamente horario de verano/invierno.
        """
        fecha = self.cleaned_data.get('fecha_entrega')
        if fecha:
            if timezone.is_naive(fecha):
                chile_tz = pytz.timezone('America/Santiago')
                # make_aware() detecta automáticamente el DST correcto para la fecha
                fecha = timezone.make_aware(fecha, chile_tz)
            return fecha
        return None
    
    def save(self, commit=True):
        """Guardar el bulto, asegurando que el estado se actualice correctamente"""
        instance = super().save(commit=False)
        
        # Si se proporcionó un estado, actualizarlo
        estado = self.cleaned_data.get('estado')
        if estado:
            instance.estado = estado
        
        if commit:
            instance.save()
        return instance


BultoEdicionFormSet = inlineformset_factory(
    Solicitud,
    Bulto,
    form=BultoEdicionAdminForm,
    extra=0,  # No agregar bultos extras en edición
    can_delete=False,  # No permitir eliminar bultos (mantener trazabilidad)
)