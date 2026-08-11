from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('solicitudes', '0010_alter_solicitud_estado'),
    ]

    operations = [
        migrations.CreateModel(
            name='Bulto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(editable=False, max_length=20, unique=True)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('embalado', 'Embalado'), ('en_ruta', 'En Ruta'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado')], default='pendiente', max_length=20)),
                ('tipo', models.CharField(choices=[('caja', 'Caja'), ('pallet', 'Pallet'), ('otro', 'Otro')], default='caja', max_length=20)),
                ('transportista', models.CharField(choices=[('PESCO', 'Camión PESCO'), ('VARMONTT', 'Varmontt'), ('STARKEN', 'Starken'), ('KAIZEN', 'Kaizen'), ('RETIRA_CLIENTE', 'Retira cliente'), ('OTRO', 'Otro / Coordinado')], default='PESCO', max_length=20)),
                ('transportista_extra', models.CharField(blank=True, max_length=100, verbose_name='Transportista externo')),
                ('numero_guia_transportista', models.CharField(blank=True, max_length=100, verbose_name='N° guía transportista')),
                ('peso_total', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('largo_cm', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('ancho_cm', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('alto_cm', models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ('observaciones', models.TextField(blank=True)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('fecha_entrega', models.DateTimeField(blank=True, null=True)),
                ('creado_por', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bultos_creados', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Bulto',
                'verbose_name_plural': 'Bultos',
                'db_table': 'despacho_bultos',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='BultoSolicitud',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comentario', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('bulto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relaciones', to='despacho.bulto')),
                ('solicitud', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='relaciones_bulto', to='solicitudes.solicitud')),
            ],
            options={
                'db_table': 'despacho_bulto_solicitudes',
                'ordering': ['id'],
            },
        ),
        migrations.AddField(
            model_name='bulto',
            name='solicitudes',
            field=models.ManyToManyField(related_name='bultos', through='despacho.BultoSolicitud', to='solicitudes.solicitud'),
        ),
    ]

