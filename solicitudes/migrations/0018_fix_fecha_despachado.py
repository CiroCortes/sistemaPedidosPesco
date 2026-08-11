from django.db import migrations, models


def fix_fecha_despachado(apps, schema_editor):
    """
    Corrige fecha_despachado para registros históricos.
    La migración anterior usó updated_at como proxy, pero ese campo coincide con
    created_at en los datos de prueba (mismo timestamp). El valor correcto es
    MAX(Bulto.fecha_envio) de bultos finalizados, que es cuando el sistema
    registra el despacho físico. Para solicitudes sin bultos finalizados con
    fecha_envio (ej: retira cliente) se mantiene updated_at como último recurso.
    """
    Solicitud = apps.get_model('solicitudes', 'Solicitud')
    Bulto = apps.get_model('despacho', 'Bulto')

    from django.db.models import Max, OuterRef, Subquery

    max_envio_sq = (
        Bulto.objects
        .filter(
            solicitud=OuterRef('pk'),
            estado='finalizado',
            fecha_envio__isnull=False,
        )
        .values('solicitud')
        .annotate(me=Max('fecha_envio'))
        .values('me')
    )

    # Sobreescribir fecha_despachado con el MAX(fecha_envio) real de los bultos
    updated = Solicitud.objects.filter(estado='despachado').update(
        fecha_despachado=Subquery(max_envio_sq)
    )

    # Fallback: solicitudes sin bultos finalizados con fecha_envio → usar updated_at
    Solicitud.objects.filter(
        estado='despachado',
        fecha_despachado__isnull=True,
    ).update(fecha_despachado=models.F('updated_at'))


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0017_add_estado_timestamps'),
        ('despacho', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(fix_fecha_despachado, reverse_code=noop_reverse),
    ]
