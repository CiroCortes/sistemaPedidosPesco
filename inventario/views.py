from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .services import StockService
from .models import CargaStock, StockSAP
from django.db.models import Sum, Count


@login_required
def cargar_stock(request):
    """Vista para cargar archivo de stock"""
    
    if request.method == 'POST':
        archivo = request.FILES.get('archivo_stock')
        
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo')
            return redirect('inventario:cargar_stock')
        
        # Validar extensión
        if not archivo.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser Excel (.xlsx o .xls)')
            return redirect('inventario:cargar_stock')
        
        # Procesar archivo
        service = StockService()
        resultado = service.procesar_archivo(
            archivo=archivo,
            usuario=request.user
        )
        
        if resultado['success']:
            messages.success(
                request,
                f"✅ {resultado['mensaje']} en {resultado['tiempo']:.1f} segundos"
            )
        else:
            messages.error(request, f"❌ {resultado['mensaje']}")
        
        return redirect('inventario:cargar_stock')
    
    # GET: Mostrar formulario
    ultima_carga = CargaStock.objects.filter(
        estado='completado'
    ).first()
    
    historial = CargaStock.objects.all()[:10]
    
    # Estadísticas
    stats = StockSAP.objects.aggregate(
        total_productos=Count('codigo', distinct=True),
        total_bodegas=Count('bodega', distinct=True),
        total_stock=Sum('stock_disponible'),
        total_valor=Sum('total'),
    )
    
    context = {
        'ultima_carga': ultima_carga,
        'historial': historial,
        'stats': stats,
    }
    
    return render(request, 'inventario/cargar_stock.html', context)


from django.core.paginator import Paginator
from django.db.models import Q

@login_required
def consultar_stock(request):
    """Vista para consultar stock con paginación y filtros"""
    query = request.GET.get('q', '')
    bodega = request.GET.get('bodega', '')
    
    # Obtener todos los registros base
    stock_list = StockSAP.objects.all().order_by('codigo', 'bodega')
    
    # Filtrar si hay búsqueda
    if query:
        stock_list = stock_list.filter(
            Q(codigo__icontains=query) | 
            Q(descripcion__icontains=query)
        )
    
    # Filtrar por bodega si se selecciona
    if bodega:
        stock_list = stock_list.filter(bodega=bodega)
    
    # Paginación: 50 items por página
    paginator = Paginator(stock_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Obtener lista de bodegas para el filtro
    bodegas = StockSAP.objects.values_list('bodega', 'bodega_nombre').distinct().order_by('bodega')
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'bodega_seleccionada': bodega,
        'bodegas': bodegas,
        'total_resultados': paginator.count
    }
    
    return render(request, 'inventario/consultar_stock.html', context)
