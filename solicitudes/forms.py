from django import forms
from django.forms import inlineformset_factory
from .models import Solicitud, SolicitudDetalle


class SolicitudForm(forms.ModelForm):
    """
    Formulario principal para el ingreso de solicitudes (solo cabecera).
    Los productos se manejan en el formset de detalles.
    """

    class Meta:
        model = Solicitud
        fields = [
            'tipo',
            'numero_pedido',
            'cliente',
            'bodega',
            'transporte',
            'observacion',
            'estado',
            'urgente',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'numero_pedido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'OF / Pedido'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre cliente'}),
            'bodega': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bodega origen'}),
            'transporte': forms.Select(attrs={'class': 'form-select'}),
            'observacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'urgente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'tipo': 'Tipo de solicitud',
            'numero_pedido': 'Número de pedido / OF',
            'cliente': 'Cliente',
            'bodega': 'Bodega',
            'transporte': 'Transporte',
            'observacion': 'Observaciones',
            'estado': 'Estado inicial',
            'urgente': '¿Es urgente?',
        }


class SolicitudDetalleForm(forms.ModelForm):
    class Meta:
        model = SolicitudDetalle
        fields = ['codigo', 'descripcion', 'cantidad']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
        labels = {
            'codigo': 'Código',
            'descripcion': 'Descripción',
            'cantidad': 'Cantidad',
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad') or 0
        if cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor a 0.')
        return cantidad


SolicitudDetalleFormSet = inlineformset_factory(
    Solicitud,
    SolicitudDetalle,
    form=SolicitudDetalleForm,
    extra=5,      # mostrar 5 líneas iniciales
    max_num=45,   # pero permitir hasta 45 en total
    can_delete=True,
)

