from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["GET"])
def pagina_diagnostico(request):
    """Página de diagnóstico para probar las funciones del modal."""
    return render(request, 'diagnostico/test_modal.html')

