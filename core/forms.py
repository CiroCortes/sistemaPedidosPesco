from django import forms
from django.contrib.auth import get_user_model
from .models import Bodega

User = get_user_model()

class BodegaForm(forms.ModelForm):
    class Meta:
        model = Bodega
        fields = ['codigo', 'nombre', 'descripcion', 'activa']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 013-01'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'activa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class AsignarBodegasForm(forms.ModelForm):
    bodegas_asignadas = forms.ModelMultipleChoiceField(
        queryset=Bodega.objects.filter(activa=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Bodegas que puede gestionar"
    )
    
    class Meta:
        model = User
        fields = ['bodegas_asignadas']


class UsuarioBaseForm(forms.ModelForm):
    bodegas_asignadas = forms.ModelMultipleChoiceField(
        queryset=Bodega.objects.filter(activa=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Bodegas asignadas"
    )
    
    class Meta:
        model = User
        fields = [
            'username',
            'nombre_completo',
            'email',
            'rol',
            'telefono',
            'is_active',
            'bodegas_asignadas',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['bodegas_asignadas'].queryset = Bodega.objects.filter(activa=True).order_by('codigo')
        self.fields['bodegas_asignadas'].widget.attrs.update({'class': 'form-check-input'})


class UsuarioCreateForm(UsuarioBaseForm):
    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    
    class Meta(UsuarioBaseForm.Meta):
        fields = UsuarioBaseForm.Meta.fields
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2
    
    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password1')
        user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
        return user


class UsuarioUpdateForm(UsuarioBaseForm):
    nueva_password1 = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    nueva_password2 = forms.CharField(
        label="Confirmar nueva contraseña",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False
    )
    
    class Meta(UsuarioBaseForm.Meta):
        fields = UsuarioBaseForm.Meta.fields
    
    def clean(self):
        cleaned_data = super().clean()
        pwd1 = cleaned_data.get('nueva_password1')
        pwd2 = cleaned_data.get('nueva_password2')
        if (pwd1 or pwd2) and pwd1 != pwd2:
            raise forms.ValidationError("Las nuevas contraseñas no coinciden.")
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self.save_m2m()
        nueva_password = self.cleaned_data.get('nueva_password1')
        if nueva_password:
            user.set_password(nueva_password)
            user.save(update_fields=['password'])
        return user