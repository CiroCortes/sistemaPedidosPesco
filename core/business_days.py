"""
Utilidades para cálculo de días hábiles en Chile.

Este módulo proporciona funciones para:
- Calcular días hábiles entre dos fechas
- Considerar feriados de Chile
- Aplicar hora de corte (14:30) para conteo de días
"""

from datetime import datetime, time, timedelta
from django.utils import timezone
import pytz


def ajustar_fecha_por_hora_corte(fecha_hora, hora_corte_str='14:30'):
    """
    Ajusta la fecha inicial según la hora de corte.
    
    Si la solicitud se crea después de la hora de corte (14:30),
    se considera que inicia el siguiente día hábil.
    
    Args:
        fecha_hora: datetime con timezone (aware)
        hora_corte_str: hora de corte en formato 'HH:MM' (default: '14:30')
    
    Returns:
        datetime ajustado al siguiente día hábil si aplica
    
    Example:
        >>> # Solicitud a las 15:00 del viernes
        >>> fecha = datetime(2026, 1, 3, 15, 0)
        >>> ajustada = ajustar_fecha_por_hora_corte(fecha)
        >>> # Retorna: lunes 6 de enero (salta fin de semana)
    """
    # Convertir a zona horaria de Chile si no lo está
    chile_tz = pytz.timezone('America/Santiago')
    if timezone.is_aware(fecha_hora):
        fecha_chile = fecha_hora.astimezone(chile_tz)
    else:
        fecha_chile = chile_tz.localize(fecha_hora)
    
    # Parsear hora de corte
    hora_corte_partes = hora_corte_str.split(':')
    hora_corte = time(int(hora_corte_partes[0]), int(hora_corte_partes[1]))
    
    # Si es después de la hora de corte, mover al siguiente día
    if fecha_chile.time() >= hora_corte:
        fecha_chile = fecha_chile + timedelta(days=1)
        # Resetear a inicio del día (00:00)
        fecha_chile = fecha_chile.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Si cae en fin de semana, mover al siguiente lunes
    while fecha_chile.weekday() >= 5:  # 5=sábado, 6=domingo
        fecha_chile = fecha_chile + timedelta(days=1)
    
    return fecha_chile


def es_dia_habil(fecha, feriados_list=None):
    """
    Verifica si una fecha es día hábil en Chile.
    
    Args:
        fecha: date o datetime
        feriados_list: lista de fechas (date) que son feriados
    
    Returns:
        bool: True si es día hábil, False si no
    """
    if feriados_list is None:
        feriados_list = []
    
    # Convertir datetime a date si es necesario
    if isinstance(fecha, datetime):
        fecha_date = fecha.date()
    else:
        fecha_date = fecha
    
    # Verificar si es fin de semana (sábado=5, domingo=6)
    if fecha_date.weekday() >= 5:
        return False
    
    # Verificar si es feriado
    if fecha_date in feriados_list:
        return False
    
    return True


def calcular_dias_habiles(fecha_inicio, fecha_fin, feriados_list=None):
    """
    Calcula el número de días hábiles entre dos fechas.
    
    Excluye:
    - Sábados y domingos
    - Feriados de Chile
    
    Args:
        fecha_inicio: datetime con timezone (aware)
        fecha_fin: datetime con timezone (aware)
        feriados_list: lista de fechas (date) que son feriados
    
    Returns:
        float: número de días hábiles (puede incluir decimales para horas)
    
    Example:
        >>> inicio = datetime(2026, 1, 5, 14, 0)  # Lunes
        >>> fin = datetime(2026, 1, 9, 10, 0)     # Viernes
        >>> dias = calcular_dias_habiles(inicio, fin)
        >>> # Retorna: ~3.83 días hábiles
    """
    if feriados_list is None:
        feriados_list = []
    
    # Convertir a zona horaria de Chile
    chile_tz = pytz.timezone('America/Santiago')
    
    if timezone.is_aware(fecha_inicio):
        fecha_inicio_chile = fecha_inicio.astimezone(chile_tz)
    else:
        fecha_inicio_chile = chile_tz.localize(fecha_inicio)
    
    if timezone.is_aware(fecha_fin):
        fecha_fin_chile = fecha_fin.astimezone(chile_tz)
    else:
        fecha_fin_chile = chile_tz.localize(fecha_fin)
    
    # Si las fechas son iguales o fecha_fin es anterior, retornar 0
    if fecha_fin_chile <= fecha_inicio_chile:
        return 0.0
    
    # Calcular días completos
    fecha_actual = fecha_inicio_chile.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_limite = fecha_fin_chile.replace(hour=0, minute=0, second=0, microsecond=0)
    
    dias_habiles_completos = 0
    
    while fecha_actual < fecha_limite:
        if es_dia_habil(fecha_actual, feriados_list):
            dias_habiles_completos += 1
        fecha_actual += timedelta(days=1)
    
    # Ajustar por horas parciales
    # Calcular fracción del primer día (si no empieza a las 00:00)
    horas_primer_dia = 0
    if fecha_inicio_chile.time() != time(0, 0):
        if es_dia_habil(fecha_inicio_chile, feriados_list):
            # Restar las horas que ya pasaron del primer día
            hora_inicio_decimal = fecha_inicio_chile.hour + fecha_inicio_chile.minute / 60
            # Asumiendo jornada de 8 horas (9:00 - 18:00)
            if hora_inicio_decimal < 9:
                horas_disponibles = 8
            elif hora_inicio_decimal > 18:
                horas_disponibles = 0
            else:
                horas_disponibles = 18 - hora_inicio_decimal
            horas_primer_dia = horas_disponibles / 8  # Como fracción de día
    
    # Calcular fracción del último día (si no termina a las 00:00)
    horas_ultimo_dia = 0
    if fecha_fin_chile.time() != time(0, 0):
        if es_dia_habil(fecha_fin_chile, feriados_list):
            # Sumar las horas trabajadas del último día
            hora_fin_decimal = fecha_fin_chile.hour + fecha_fin_chile.minute / 60
            # Asumiendo jornada de 9:00 - 18:00
            if hora_fin_decimal <= 9:
                horas_trabajadas = 0
            elif hora_fin_decimal >= 18:
                horas_trabajadas = 8
            else:
                horas_trabajadas = hora_fin_decimal - 9
            horas_ultimo_dia = horas_trabajadas / 8  # Como fracción de día
    
    # Total de días hábiles con fracciones
    total_dias_habiles = dias_habiles_completos + horas_ultimo_dia
    
    # Si el inicio y fin están en el mismo día
    if fecha_inicio_chile.date() == fecha_fin_chile.date():
        if es_dia_habil(fecha_inicio_chile, feriados_list):
            delta_horas = (fecha_fin_chile - fecha_inicio_chile).total_seconds() / 3600
            # Convertir horas a fracción de jornada (8 horas)
            total_dias_habiles = delta_horas / 8
        else:
            total_dias_habiles = 0.0
    
    return max(0.0, total_dias_habiles)


def obtener_feriados_chile(año=None):
    """
    Obtiene la lista de feriados de Chile desde la base de datos.
    
    Args:
        año: año específico (int), si es None usa el año actual
    
    Returns:
        list: lista de objetos date con los feriados
    """
    from configuracion.models import Feriado
    from datetime import date
    
    if año is None:
        año = date.today().year
    
    # Obtener feriados del año desde la BD
    feriados = Feriado.objects.filter(
        fecha__year=año,
        activo=True
    ).values_list('fecha', flat=True)
    
    return list(feriados)

