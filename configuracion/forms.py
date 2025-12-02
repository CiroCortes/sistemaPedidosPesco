from django import forms

from .models import EstadoWorkflow, TransporteConfig


class EstadoWorkflowForm(forms.ModelForm):
    class Meta:
        model = EstadoWorkflow
        fields = [
            'tipo',
            'slug',
            'nombre',
            'descripcion',
            'orden',
            'color',
            'icono',
            'activo',
            'es_terminal',
        ]
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: pendiente'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bootstrap color o hex'}),
            'icono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Icono Bootstrap, ej: truck'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_terminal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, disable_slug=False, **kwargs):
        super().__init__(*args, **kwargs)
        if disable_slug:
            self.fields['slug'].disabled = True


class TransporteConfigForm(forms.ModelForm):
    class Meta:
        model = TransporteConfig
        fields = [
            'slug',
            'nombre',
            'descripcion',
            'orden',
            'es_propio',
            'activo',
            'requiere_ot',
        ]
        widgets = {
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ej: PESCO'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'orden': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'es_propio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requiere_ot': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, disable_slug=False, **kwargs):
        super().__init__(*args, **kwargs)
        if disable_slug:
            self.fields['slug'].disabled = True

