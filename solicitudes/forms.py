from django import forms
from django.forms import inlineformset_factory

from core.models import Bodega
from configuracion.models import TransporteConfig, EstadoWorkflow, TipoSolicitud
from .models import Solicitud, SolicitudDetalle

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
