from django.db import migrations


def drop_slug_constraint(apps, schema_editor):
    """Elimina la constraint única del slug antes de hacer el seed"""
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'config_estados_slug_key'
                    ) THEN
                        ALTER TABLE config_estados DROP CONSTRAINT config_estados_slug_key;
                    END IF;
                END $$;
            """)


def seed_estados(apps, schema_editor):
    EstadoWorkflow = apps.get_model('configuracion', 'EstadoWorkflow')

    defaults = [
        # Solicitud
        ('solicitud', 'pendiente', 'Pendiente', 'warning', 'clock', 10),
        ('solicitud', 'en_despacho', 'En Despacho', 'info', 'truck', 20),
        ('solicitud', 'embalado', 'Embalado', 'success', 'box-seam', 30),
        ('solicitud', 'listo_despacho', 'Listo para Despacho', 'primary', 'flag', 40),
        ('solicitud', 'en_ruta', 'En Ruta', 'primary', 'truck-front', 50),
        ('solicitud', 'despachado', 'Despachado', 'dark', 'check-circle', 60),
        ('solicitud', 'cancelado', 'Cancelado', 'danger', 'x-circle', 70),
        # Detalle
        ('detalle', 'pendiente', 'Pendiente', 'warning', 'clock-history', 10),
        ('detalle', 'preparando', 'Preparando', 'info', 'tools', 20),
        ('detalle', 'preparado', 'Preparado', 'success', 'check2', 30),
        # Bulto
        ('bulto', 'pendiente', 'Pendiente', 'secondary', 'box', 10),
        ('bulto', 'embalado', 'Embalado', 'success', 'box-seam', 20),
        ('bulto', 'en_ruta', 'En Ruta', 'primary', 'truck', 30),
        ('bulto', 'entregado', 'Entregado', 'dark', 'check-circle', 40),
        ('bulto', 'cancelado', 'Cancelado', 'danger', 'x-circle', 50),
    ]

    for tipo, slug, nombre, color, icono, orden in defaults:
        EstadoWorkflow.objects.update_or_create(
            tipo=tipo,
            slug=slug,
            defaults={
                'nombre': nombre,
                'color': color,
                'icono': icono,
                'orden': orden,
                'activo': True,
            },
        )


def seed_transportes(apps, schema_editor):
    TransporteConfig = apps.get_model('configuracion', 'TransporteConfig')

    defaults = [
        ('PESCO', 'Camión PESCO', True, False, 10),
        ('VARMONTT', 'Varmontt', False, False, 20),
        ('STARKEN', 'Starken', False, True, 30),
        ('KAIZEN', 'Kaizen', False, True, 40),
        ('RETIRA_CLIENTE', 'Retira cliente', False, False, 50),
        ('OTRO', 'Otro coordinado', False, True, 60),
    ]

    for slug, nombre, es_propio, requiere_ot, orden in defaults:
        TransporteConfig.objects.update_or_create(
            slug=slug,
            defaults={
                'nombre': nombre,
                'es_propio': es_propio,
                'requiere_ot': requiere_ot,
                'orden': orden,
                'activo': True,
            },
        )


def forwards(apps, schema_editor):
    drop_slug_constraint(apps, schema_editor)  # Primero eliminar constraint
    seed_estados(apps, schema_editor)
    seed_transportes(apps, schema_editor)


def rollback(apps, schema_editor):
    EstadoWorkflow = apps.get_model('configuracion', 'EstadoWorkflow')
    TransporteConfig = apps.get_model('configuracion', 'TransporteConfig')
    EstadoWorkflow.objects.all().delete()
    TransporteConfig.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracion', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, rollback),
    ]

