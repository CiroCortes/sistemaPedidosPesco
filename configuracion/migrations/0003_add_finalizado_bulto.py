from django.db import migrations


def add_finalizado_bulto(apps, schema_editor):
    """Agrega el estado 'finalizado' para bultos"""
    EstadoWorkflow = apps.get_model('configuracion', 'EstadoWorkflow')
    
    # Crear estado 'finalizado' para bultos
    EstadoWorkflow.objects.update_or_create(
        tipo='bulto',
        slug='finalizado',
        defaults={
            'nombre': 'Finalizado',
            'color': 'success',
            'icono': 'check-all',
            'orden': 60,  # Después de entregado
            'activo': True,
            'es_terminal': True,  # Estado terminal/cerrado
        },
    )
    
    # También asegurar que existe 'listo_despacho' para bultos (por si no existe)
    EstadoWorkflow.objects.update_or_create(
        tipo='bulto',
        slug='listo_despacho',
        defaults={
            'nombre': 'Listo para Despacho',
            'color': 'primary',
            'icono': 'flag',
            'orden': 25,  # Entre embalado y en_ruta
            'activo': True,
            'es_terminal': False,
        },
    )


def remove_finalizado_bulto(apps, schema_editor):
    """Elimina el estado 'finalizado' de bultos (rollback)"""
    EstadoWorkflow = apps.get_model('configuracion', 'EstadoWorkflow')
    EstadoWorkflow.objects.filter(tipo='bulto', slug='finalizado').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0002_seed_defaults'),
    ]

    operations = [
        migrations.RunPython(add_finalizado_bulto, remove_finalizado_bulto),
    ]

