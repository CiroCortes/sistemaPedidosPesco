from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0011_solicituddetalle_bulto'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicitud',
            name='numero_ot',
            field=models.CharField(blank=True, help_text='Orden de transporte asignada por el transportista externo', max_length=100, verbose_name='Número OT'),
        ),
        migrations.AlterField(
            model_name='solicitud',
            name='estado',
            field=models.CharField(choices=[('pendiente', 'Pendiente'), ('en_despacho', 'En Despacho'), ('embalado', 'Embalado'), ('listo_despacho', 'Listo para Despacho'), ('en_ruta', 'En Ruta'), ('despachado', 'Despachado'), ('cancelado', 'Cancelado')], db_index=True, default='pendiente', max_length=20, verbose_name='Estado'),
        ),
        migrations.AddIndex(
            model_name='solicitud',
            index=models.Index(fields=['numero_ot'], name='idx_numero_ot'),
        ),
    ]

