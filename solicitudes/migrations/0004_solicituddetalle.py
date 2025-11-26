from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0003_rename_solicitudes_tipo_crea_idx_solicitudes_tipo_a7b99a_idx'),
    ]

    operations = [
        migrations.CreateModel(
            name='SolicitudDetalle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=50, verbose_name='Código de producto')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('cantidad', models.PositiveIntegerField(verbose_name='Cantidad')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Creado el')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='solicitudes.solicitud', verbose_name='Solicitud')),
            ],
            options={
                'verbose_name': 'Detalle de solicitud',
                'verbose_name_plural': 'Detalles de solicitud',
                'db_table': 'solicitudes_detalle',
                'ordering': ['id'],
            },
        ),
        migrations.AddIndex(
            model_name='solicituddetalle',
            index=models.Index(fields=['solicitud', 'codigo'], name='solicitude_solicitu_5c39e4_idx'),
        ),
    ]


