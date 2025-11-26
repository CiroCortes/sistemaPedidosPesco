from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from core.decorators import role_required
from .models import Stock, CargaStock
from .services import procesar_archivo_stock

@login_required
@role_required(['admin'])
def cargar_stock(request):
    """
    Vista para que el admin suba el archivo de stock diario.
    """
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, "Debes seleccionar un archivo.")
            return redirect('bodega:cargar_stock')
            
        if not archivo.name.endswith(('.xls', '.xlsx')):
            messages.error(request, "Formato no válido. Usa Excel (.xlsx, .xls)")
            return redirect('bodega:cargar_stock')
            
        try:
            resultado = procesar_archivo_stock(archivo, request.user)
            messages.success(
                request, 
                f"✅ Stock cargado correctamente. "
                f"Productos: {resultado['total_productos']}, "
                f"Bodegas: {resultado['total_bodegas']}"
            )
            if resultado.get('errores_fila', 0) > 0:
                messages.warning(request, f"⚠️ Hubo {resultado['errores_fila']} filas con errores que se omitieron.")
                
            return redirect('bodega:historial_cargas')
        except Exception as e:
            messages.error(request, f"❌ Error al procesar archivo: {e}")
            
    # Mostrar última carga activa
    ultima_carga = CargaStock.objects.filter(estado='activo').first()
    
    return render(request, 'bodega/cargar_stock.html', {
        'ultima_carga': ultima_carga
    })

@login_required
def consultar_stock(request):
    """
    Vista para consultar stock disponible.
    Accesible para todos los roles.
    """
    query = request.GET.get('q', '')
    bodega = request.GET.get('bodega', '')
    
    stock_list = Stock.objects.all()
    
    if query:
        stock_list = stock_list.filter(
            Q(codigo__icontains=query) | 
            Q(descripcion__icontains=query)
        )
        
    if bodega:
        stock_list = stock_list.filter(bodega=bodega)
        
    # Paginación
    paginator = Paginator(stock_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener lista de bodegas para el filtro
    bodegas = Stock.objects.values_list('bodega', 'bodega_nombre').distinct().order_by('bodega')
    
    return render(request, 'bodega/consultar_stock.html', {
        'page_obj': page_obj,
        'query': query,
        'bodega_seleccionada': bodega,
        'bodegas': bodegas
    })

@login_required
@role_required(['admin'])
def historial_cargas(request):
    """
    Historial de cargas de archivos de stock.
    """
    cargas = CargaStock.objects.all()
    paginator = Paginator(cargas, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'bodega/historial_cargas.html', {
        'page_obj': page_obj
    })
