# Generated migration to convert ManyToManyField to ForeignKey

from django.db import migrations, models
import django.db.models.deletion


def migrate_solicitudes_to_foreignkey(apps, schema_editor):
    """Migrar datos de ManyToMany a ForeignKey"""
    Bulto = apps.get_model('despacho', 'Bulto')
    BultoSolicitud = apps.get_model('despacho', 'BultoSolicitud')
    
    # Para cada bulto, tomar la primera solicitud relacionada
    for bulto in Bulto.objects.all():
        relacion = BultoSolicitud.objects.filter(bulto=bulto).first()
        if relacion:
            # Actualizar el nuevo campo ForeignKey
            bulto.solicitud = relacion.solicitud
            bulto.save(update_fields=['solicitud'])


class Migration(migrations.Migration):

    dependencies = [
        ('despacho', '0003_add_fecha_embalaje'),
        ('solicitudes', '0011_solicituddetalle_bulto'),  # Migración que agrega ForeignKey bulto a SolicitudDetalle
    ]

    operations = [
        # Paso 1: Agregar nuevo campo ForeignKey (nullable temporalmente para migración)
        migrations.AddField(
            model_name='bulto',
            name='solicitud',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bultos',
                to='solicitudes.solicitud',
                verbose_name='Solicitud'
            ),
        ),
        # Paso 2: Migrar datos desde BultoSolicitud
        migrations.RunPython(
            migrate_solicitudes_to_foreignkey,
            reverse_code=migrations.RunPython.noop
        ),
        # Paso 3: Hacer el campo NOT NULL
        migrations.AlterField(
            model_name='bulto',
            name='solicitud',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bultos',
                to='solicitudes.solicitud',
                verbose_name='Solicitud'
            ),
        ),
        # Paso 4: Eliminar el ManyToManyField
        migrations.RemoveField(
            model_name='bulto',
            name='solicitudes',
        ),
        # Paso 5: Eliminar tabla intermedia
        migrations.DeleteModel(
            name='BultoSolicitud',
        ),
    ]

