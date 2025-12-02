from django import forms


class TransferenciaForm(forms.Form):
    numero_transferencia = forms.CharField(
        label="N° transferencia SAP",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ej: 4500001234'
        })
    )
    fecha_transferencia = forms.DateField(
        label="Fecha de entrega",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    hora_transferencia = forms.TimeField(
        label="Hora de entrega",
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    bodega_destino = forms.CharField(
        label="Bodega destino",
        max_length=50,
        initial='013',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

