from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import pytz

from configuracion.models import EstadoWorkflow, TransporteConfig
from .models import Bulto


class BultoForm(forms.ModelForm):
    solicitudes = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Bulto
        fields = [
            'tipo',
            'transportista',
            'transportista_extra',
            'numero_guia_transportista',
            'peso_total',
            'largo_cm',
            'ancho_cm',
            'alto_cm',
            'observaciones',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'transportista': forms.Select(attrs={'class': 'form-select'}),
            'transportista_extra': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Solo si es OTRO'}),
            'numero_guia_transportista': forms.TextInput(attrs={'class': 'form-control'}),
            'peso_total': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'largo_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'ancho_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'alto_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['transportista'].choices = self._transportes_choices()

    def _transportes_choices(self):
        choices = [(t.slug, t.nombre) for t in TransporteConfig.activos()]
        if not choices:
            choices = [('PESCO', 'Camión PESCO')]
        return choices


class BultoEstadoForm(forms.ModelForm):
    class Meta:
        model = Bulto
        fields = ['estado', 'numero_guia_transportista', 'fecha_embalaje']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'numero_guia_transportista': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Opcional'}),
            'fecha_embalaje': forms.DateTimeInput(attrs={
                'type': 'datetime-local', 
                'class': 'form-control',
                'placeholder': 'Solo si está embalado'
            }),
        }
        labels = {
            'estado': 'Estado',
            'numero_guia_transportista': 'N° guía transportista',
            'fecha_embalaje': 'Fecha embalaje',
        }
        help_texts = {
            'fecha_embalaje': 'Fecha y hora cuando se embaló el bulto. Las fechas de despacho y entrega se gestionan desde solicitudes.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estados = EstadoWorkflow.activos_para(EstadoWorkflow.TIPO_BULTO)
        self.fields['estado'].choices = [(e.slug, e.nombre) for e in estados]
        
        # Hacer fecha_embalaje opcional
        self.fields['fecha_embalaje'].required = False
        self.fields['numero_guia_transportista'].required = False
    
    def clean_fecha_embalaje(self):
        """
        Convierte fecha naive del navegador a aware con zona horaria de Chile.
        fecha_embalaje es la fecha real del proceso (fecha_creacion del bulto no afecta el KPI).
        """
        fecha_embalaje = self.cleaned_data.get('fecha_embalaje')
        if fecha_embalaje:
            # Convertir a zona horaria de Chile si es naive
            if timezone.is_naive(fecha_embalaje):
                chile_tz = pytz.timezone('America/Santiago')
                fecha_embalaje = timezone.make_aware(fecha_embalaje, chile_tz)
            
            return fecha_embalaje
        return None

