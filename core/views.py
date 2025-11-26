"""
Vistas principales del Sistema PESCO
Basado en la arquitectura de sistemaGDV
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from solicitudes.models import Solicitud
from .models import Usuario


def login_view(request):
    """
    Vista de login
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Bienvenido {user.nombre_completo}')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'login.html')


def logout_view(request):
    """
    Vista de logout
    """
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente')
    return redirect('login')


@login_required
def dashboard(request):
    """
    Dashboard principal
    Muestra diferentes métricas según el rol del usuario
    """
    user = request.user
    context = {
        'user': user,
        'hoy': timezone.now().date(),
    }
    
    if user.es_admin():
        # Admin ve todo
        context.update({
            'total_solicitudes': Solicitud.objects.count(),
            'solicitudes_pendientes': Solicitud.objects.filter(estado='pendiente').count(),
            'solicitudes_en_despacho': Solicitud.objects.filter(estado='en_despacho').count(),
            'solicitudes_embaladas': Solicitud.objects.filter(estado='embalado').count(),
            'solicitudes_urgentes': Solicitud.objects.filter(
                urgente=True, 
                estado__in=['pendiente', 'en_despacho', 'embalado']
            ).count(),
            'solicitudes_recientes': Solicitud.objects.select_related('solicitante')[:10],
            
            # Estadísticas por estado
            'stats_por_estado': Solicitud.objects.values('estado').annotate(
                total=Count('id')
            ).order_by('estado'),
        })
    
    elif user.es_bodega():
        # Bodega solo ve pendientes
        solicitudes_pendientes = Solicitud.objects.filter(estado='pendiente').select_related('solicitante')
        
        context.update({
            'solicitudes_pendientes': solicitudes_pendientes.count(),
            'solicitudes_urgentes': solicitudes_pendientes.filter(urgente=True).count(),
            'listado_solicitudes': solicitudes_pendientes[:15],
        })
    
    elif user.es_despacho():
        # Despacho solo ve en_despacho
        solicitudes_en_despacho = Solicitud.objects.filter(estado='en_despacho').select_related('solicitante')
        
        context.update({
            'solicitudes_en_despacho': solicitudes_en_despacho.count(),
            'solicitudes_urgentes': solicitudes_en_despacho.filter(urgente=True).count(),
            'listado_solicitudes': solicitudes_en_despacho[:15],
        })
    
    return render(request, 'dashboard.html', context)


@login_required
def perfil_usuario(request):
    """
    Vista del perfil del usuario
    """
    user = request.user

    if request.method == 'POST':
        # Solo administradores y superusuarios pueden cambiar su rol
        if user.es_admin():
            nuevo_rol = request.POST.get('rol')
            roles_validos = [rol[0] for rol in Usuario.ROLES]

            if nuevo_rol in roles_validos:
                user.rol = nuevo_rol
                user.save(update_fields=['rol'])
                messages.success(request, f'Rol actualizado a {user.get_rol_display()}')
            else:
                messages.error(request, 'Rol seleccionado no es válido')
        else:
            messages.error(request, 'No tienes permisos para cambiar el rol')

        return redirect('perfil')

    context = {
        'user': user,
        'roles': Usuario.ROLES,
    }
    return render(request, 'perfil.html', context)
