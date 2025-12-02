from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.decorators import role_required
from .forms import EstadoWorkflowForm, TransporteConfigForm
from .models import EstadoWorkflow, TransporteConfig


@login_required
@role_required(['admin'])
def lista_estados(request):
    estados = EstadoWorkflow.objects.order_by('tipo', 'orden')
    form = EstadoWorkflowForm()
    return render(request, 'configuracion/estados_lista.html', {
        'estados': estados,
        'form': form,
    })


@login_required
@role_required(['admin'])
def crear_estado(request):
    if request.method != 'POST':
        return redirect('configuracion:lista_estados')
    form = EstadoWorkflowForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Estado creado correctamente.')
    else:
        messages.error(request, 'Corrige los errores del formulario.')
    return redirect('configuracion:lista_estados')


@login_required
@role_required(['admin'])
def editar_estado(request, pk):
    estado = get_object_or_404(EstadoWorkflow, pk=pk)
    if request.method == 'POST':
        form = EstadoWorkflowForm(request.POST, instance=estado, disable_slug=True)
        if form.is_valid():
            form.save()
            messages.success(request, 'Estado actualizado.')
            return redirect('configuracion:lista_estados')
        messages.error(request, 'Errores al actualizar el estado.')
    else:
        form = EstadoWorkflowForm(instance=estado, disable_slug=True)
    return render(request, 'configuracion/estado_form.html', {
        'form': form,
        'estado': estado,
    })


@login_required
@role_required(['admin'])
def toggle_estado(request, pk):
    estado = get_object_or_404(EstadoWorkflow, pk=pk)
    estado.activo = not estado.activo
    estado.save(update_fields=['activo'])
    return redirect('configuracion:lista_estados')


@login_required
@role_required(['admin'])
def lista_transportes(request):
    transportes = TransporteConfig.objects.order_by('orden', 'nombre')
    form = TransporteConfigForm()
    return render(request, 'configuracion/transportes_lista.html', {
        'transportes': transportes,
        'form': form,
    })


@login_required
@role_required(['admin'])
def crear_transporte(request):
    if request.method != 'POST':
        return redirect('configuracion:lista_transportes')
    form = TransporteConfigForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Transporte creado correctamente.')
    else:
        messages.error(request, 'Corrige los errores del formulario.')
    return redirect('configuracion:lista_transportes')


@login_required
@role_required(['admin'])
def editar_transporte(request, pk):
    transporte = get_object_or_404(TransporteConfig, pk=pk)
    if request.method == 'POST':
        form = TransporteConfigForm(request.POST, instance=transporte, disable_slug=True)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transporte actualizado.')
            return redirect('configuracion:lista_transportes')
        messages.error(request, 'Errores al actualizar el transporte.')
    else:
        form = TransporteConfigForm(instance=transporte, disable_slug=True)
    return render(request, 'configuracion/transporte_form.html', {
        'form': form,
        'transporte': transporte,
    })


@login_required
@role_required(['admin'])
def toggle_transporte(request, pk):
    transporte = get_object_or_404(TransporteConfig, pk=pk)
    transporte.activo = not transporte.activo
    transporte.save(update_fields=['activo'])
    return redirect('configuracion:lista_transportes')

