from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from core.decorators import role_required
from .models import Bodega
from .forms import BodegaForm, AsignarBodegasForm

User = get_user_model()

@login_required
@role_required(['admin'])
def lista_bodegas(request):
    """Lista todas las bodegas del sistema"""
    bodegas = Bodega.objects.all().prefetch_related('usuarios').order_by('codigo')
    return render(request, 'bodegas/lista.html', {'bodegas': bodegas})

@login_required
@role_required(['admin'])
def crear_bodega(request):
    """Crea una nueva bodega"""
    if request.method == 'POST':
        form = BodegaForm(request.POST)
        if form.is_valid():
            bodega = form.save()
            messages.success(request, f'Bodega {bodega.codigo} creada correctamente.')
            return redirect('lista_bodegas')
    else:
        form = BodegaForm()
    
    return render(request, 'bodegas/formulario.html', {
        'form': form,
        'titulo': 'Nueva Bodega'
    })

@login_required
@role_required(['admin'])
def editar_bodega(request, pk):
    """Edita una bodega existente"""
    bodega = get_object_or_404(Bodega, pk=pk)
    if request.method == 'POST':
        form = BodegaForm(request.POST, instance=bodega)
        if form.is_valid():
            form.save()
            messages.success(request, f'Bodega {bodega.codigo} actualizada.')
            return redirect('lista_bodegas')
    else:
        form = BodegaForm(instance=bodega)
    
    return render(request, 'bodegas/formulario.html', {
        'form': form,
        'titulo': f'Editar Bodega {bodega.codigo}'
    })

@login_required
@role_required(['admin'])
def lista_usuarios_bodegas(request):
    """Lista usuarios y sus bodegas asignadas"""
    # Solo mostrar usuarios que no son admin (o todos si se prefiere)
    usuarios = User.objects.exclude(rol='admin').prefetch_related('bodegas_asignadas')
    return render(request, 'bodegas/usuarios.html', {'usuarios': usuarios})

@login_required
@role_required(['admin'])
def asignar_bodegas(request, user_id):
    """Asigna bodegas a un usuario específico"""
    usuario = get_object_or_404(User, pk=user_id)
    
    if request.method == 'POST':
        form = AsignarBodegasForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Bodegas asignadas a {usuario.nombre_completo or usuario.username}.')
            return redirect('lista_usuarios_bodegas')
    else:
        form = AsignarBodegasForm(instance=usuario)
    
    return render(request, 'bodegas/asignar.html', {
        'form': form,
        'usuario': usuario
    })


@login_required
@role_required(['admin'])
def toggle_estado_bodega(request, pk):
    """Activa o desactiva una bodega de forma rápida desde la tabla."""
    bodega = get_object_or_404(Bodega, pk=pk)
    
    if request.method == 'POST':
        bodega.activa = not bodega.activa
        bodega.save(update_fields=['activa'])
        estado = "activada" if bodega.activa else "desactivada"
        messages.success(request, f'Bodega {bodega.codigo} {estado} para la operación.')
    else:
        messages.warning(request, 'Acción no permitida.')
    
    return redirect('lista_bodegas')