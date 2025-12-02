from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import role_required
from .forms import UsuarioCreateForm, UsuarioUpdateForm

User = get_user_model()


@login_required
@role_required(['admin'])
def lista_usuarios(request):
    """Lista todos los usuarios con filtros por rol y búsqueda."""
    rol = request.GET.get('rol', '')
    busqueda = request.GET.get('q', '')

    usuarios = User.objects.all().order_by('username')

    if rol:
        usuarios = usuarios.filter(rol=rol)
    if busqueda:
        usuarios = usuarios.filter(
            Q(username__icontains=busqueda)
            | Q(nombre_completo__icontains=busqueda)
            | Q(email__icontains=busqueda)
        )

    context = {
        'usuarios': usuarios,
        'rol': rol,
        'busqueda': busqueda,
        'roles': User.ROLES,
    }
    return render(request, 'usuarios/lista.html', context)


@login_required
@role_required(['admin'])
def crear_usuario(request):
    """Permite crear un nuevo usuario con rol y bodegas asignadas."""
    if request.method == 'POST':
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            messages.success(request, f'Usuario {usuario.username} creado correctamente.')
            return redirect('lista_usuarios')
    else:
        form = UsuarioCreateForm(initial={'is_active': True})

    return render(request, 'usuarios/formulario.html', {
        'form': form,
        'titulo': 'Nuevo usuario',
        'modo_creacion': True,
    })


@login_required
@role_required(['admin'])
def editar_usuario(request, pk):
    """Editar los datos de un usuario existente."""
    usuario = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UsuarioUpdateForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario {usuario.username} actualizado.')
            return redirect('lista_usuarios')
    else:
        form = UsuarioUpdateForm(instance=usuario)

    return render(request, 'usuarios/formulario.html', {
        'form': form,
        'titulo': f'Editar {usuario.username}',
        'modo_creacion': False,
        'usuario_obj': usuario,
    })

