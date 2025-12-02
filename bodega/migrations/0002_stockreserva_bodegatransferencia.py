from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import bodega.models


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0009_solicituddetalle_bodega_and_more'),
        ('bodega', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockReserva',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=50)),
                ('bodega', models.CharField(max_length=50)),
                ('cantidad', models.PositiveIntegerField()),
                ('estado', models.CharField(choices=[('reservada', 'Reservada'), ('consumida', 'Consumida'), ('liberada', 'Liberada')], default='reservada', max_length=20)),
                ('observacion', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('detalle', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reserva', to='solicitudes.solicituddetalle')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reservas', to='solicitudes.solicitud')),
            ],
            options={
                'db_table': 'bodega_stock_reservas',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BodegaTransferencia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_transferencia', models.CharField(max_length=50, unique=True)),
                ('fecha_transferencia', models.DateField(default=bodega.models.get_local_date)),
                ('hora_transferencia', models.TimeField(default=bodega.models.get_local_time)),
                ('bodega_origen', models.CharField(max_length=50)),
                ('bodega_destino', models.CharField(default='013', max_length=50)),
                ('cantidad', models.PositiveIntegerField()),
                ('observaciones', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('detalle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transferencias', to='solicitudes.solicituddetalle')),
                ('registrado_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transferencias_registradas', to=settings.AUTH_USER_MODEL)),
                ('reserva', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='transferencias', to='bodega.stockreserva')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transferencias', to='solicitudes.solicitud')),
            ],
            options={
                'db_table': 'bodega_transferencias',
                'ordering': ['-fecha_transferencia', '-hora_transferencia'],
            },
        ),
        migrations.AddIndex(
            model_name='stockreserva',
            index=models.Index(fields=['codigo', 'bodega'], name='bodega_reserva_cod_bod'),
        ),
        migrations.AddIndex(
            model_name='stockreserva',
            index=models.Index(fields=['estado'], name='bodega_reserva_estado'),
        ),
        migrations.AddIndex(
            model_name='bodegatransferencia',
            index=models.Index(fields=['numero_transferencia'], name='bodega_transfer_numero'),
        ),
        migrations.AddIndex(
            model_name='bodegatransferencia',
            index=models.Index(fields=['fecha_transferencia', 'hora_transferencia'], name='bodega_transfer_fecha_hora'),
        ),
        migrations.AddIndex(
            model_name='bodegatransferencia',
            index=models.Index(fields=['bodega_origen'], name='bodega_transfer_origen'),
        ),
    ]

