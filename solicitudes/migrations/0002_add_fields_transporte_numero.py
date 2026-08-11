from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitud',
            name='numero_pedido',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='Número de pedido / OF'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='solicitud',
            name='numero_st',
            field=models.CharField(blank=True, default='', editable=False, max_length=20, verbose_name='Número ST automático'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='solicitud',
            name='transporte',
            field=models.CharField(choices=[('PESCO', 'Camión PESCO'), ('VARMONTT', 'Varmontt'), ('STARKEN', 'Starken'), ('KAIZEN', 'Kaizen'), ('OTRO', 'Otro / Coordinado')], default='PESCO', max_length=20, verbose_name='Transporte'),
        ),
        migrations.AlterField(
            model_name='solicitud',
            name='tipo',
            field=models.CharField(choices=[('PC', 'PC'), ('OC', 'OC'), ('EM', 'Emergencia'), ('ST', 'Solicitud de Traslado'), ('OF', 'Oficina'), ('RM', 'Retiro de Mercancías')], max_length=2, verbose_name='Tipo de solicitud'),
        ),
        migrations.AddIndex(
            model_name='solicitud',
            index=models.Index(fields=['tipo', 'created_at'], name='solicitudes_tipo_crea_idx'),
        ),
    ]

