from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0009_solicituddetalle_bodega_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='solicitud',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('en_despacho', 'En Despacho'), ('embalado', 'Embalado'), ('en_ruta', 'En Ruta'), ('despachado', 'Despachado'), ('cancelado', 'Cancelado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado'),
        ),
    ]

