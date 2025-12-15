from django import template

register = template.Library()


@register.filter
def formato_numero(valor):
    """
    Formatea números grandes con nomenclatura abreviada:
    - >= 1,000,000: M (millones)
    - >= 1,000: K (miles)
    - < 1,000: número normal
    """
    if valor is None:
        return '0'
    
    try:
        num = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    
    if num == 0:
        return '0'
    
    abs_num = abs(num)
    sign = '-' if num < 0 else ''
    
    if abs_num >= 1_000_000:
        formatted = f"{abs_num / 1_000_000:.1f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted}M"
    elif abs_num >= 1_000:
        formatted = f"{abs_num / 1_000:.1f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted}K"
    else:
        return f"{sign}{int(abs_num)}"


@register.filter
def formato_usd(valor):
    """
    Formatea valores monetarios en USD con nomenclatura abreviada:
    - >= 1,000,000: 23M USD
    - >= 1,000: 1.5K USD
    - < 1,000: 500 USD
    """
    if valor is None:
        return '0 USD'
    
    try:
        num = float(valor)
    except (TypeError, ValueError):
        return f'{valor} USD'
    
    if num == 0:
        return '0 USD'
    
    abs_num = abs(num)
    sign = '-' if num < 0 else ''
    
    if abs_num >= 1_000_000:
        formatted = f"{abs_num / 1_000_000:.1f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted}M USD"
    elif abs_num >= 1_000:
        formatted = f"{abs_num / 1_000:.1f}".rstrip('0').rstrip('.')
        return f"{sign}{formatted}K USD"
    else:
        return f"{sign}{int(abs_num)} USD"

