from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Esta migración se aplica después de la 0005 que renombra índices
        ('solicitudes', '0005_rename_solicitude_solicitu_5c39e4_idx_solicitudes_solicit_0ab720_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='solicitud',
            name='bodega',
            field=models.CharField(
                max_length=50,
                blank=True,
                verbose_name='Bodega origen',
            ),
        ),
    ]


