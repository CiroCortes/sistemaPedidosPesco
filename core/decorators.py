"""
Decoradores de seguridad para Sistema PESCO
Basado en la arquitectura de sistemaGDV
"""

from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles):
    """
    Decorador para proteger vistas por rol
    
    Uso:
        @role_required(['admin', 'bodega'])
        def mi_vista(request):
            ...
    
    Args:
        allowed_roles (list): Lista de roles permitidos
    
    Returns:
        function: Vista decorada
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.rol in allowed_roles:
                return view_func(request, *args, **kwargs)
            
            messages.error(request, 'No tienes permisos para acceder a esta página')
            return HttpResponseForbidden(
                "<h1>403 Prohibido</h1>"
                "<p>No tienes permisos para acceder a esta página.</p>"
                f"<p>Tu rol: {request.user.get_rol_display()}</p>"
                f"<p>Roles permitidos: {', '.join(allowed_roles)}</p>"
            )
        return wrapper
    return decorator


def admin_only(view_func):
    """
    Decorador para vistas solo de administrador
    
    Uso:
        @admin_only
        def mi_vista_admin(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.es_admin():
            return view_func(request, *args, **kwargs)
        
        messages.warning(request, 'Esta sección es solo para administradores')
        return redirect('dashboard')
    return wrapper


def bodega_only(view_func):
    """
    Decorador para vistas solo de bodega
    (Admin también puede acceder)
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.es_admin() or request.user.es_bodega():
            return view_func(request, *args, **kwargs)
        
        messages.warning(request, 'Esta sección es solo para personal de bodega')
        return redirect('dashboard')
    return wrapper


def despacho_only(view_func):
    """
    Decorador para vistas solo de despacho
    (Admin también puede acceder)
    """
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.es_admin() or request.user.es_despacho():
            return view_func(request, *args, **kwargs)
        
        messages.warning(request, 'Esta sección es solo para personal de despacho')
        return redirect('dashboard')
    return wrapper


def ajax_required(view_func):
    """
    Decorador para vistas que solo aceptan peticiones AJAX
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden('Solo peticiones AJAX permitidas')
    return wrapper

