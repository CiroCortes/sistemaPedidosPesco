from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0012_alter_solicitud_estado_numero_ot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='solicitud',
            name='estado',
            field=models.CharField(db_index=True, default='pendiente', max_length=50, verbose_name='Estado'),
        ),
        migrations.AlterField(
            model_name='solicitud',
            name='transporte',
            field=models.CharField(default='PESCO', max_length=50, verbose_name='Transporte'),
        ),
        migrations.AlterField(
            model_name='solicituddetalle',
            name='estado_bodega',
            field=models.CharField(db_index=True, default='pendiente', max_length=30, verbose_name='Estado en bodega'),
        ),
    ]

