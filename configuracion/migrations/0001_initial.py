from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EstadoWorkflow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=50, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.TextField(blank=True)),
                ('tipo', models.CharField(choices=[('solicitud', 'Solicitudes'), ('detalle', 'Detalle de bodega'), ('bulto', 'Bultos')], max_length=20)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('color', models.CharField(default='secondary', max_length=30)),
                ('icono', models.CharField(default='circle', max_length=50)),
                ('activo', models.BooleanField(default=True)),
                ('es_terminal', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Estado configurable',
                'verbose_name_plural': 'Estados configurables',
                'ordering': ['tipo', 'orden'],
                'db_table': 'config_estados',
                'unique_together': {('tipo', 'slug')},
            },
        ),
        migrations.CreateModel(
            name='TransporteConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slug', models.SlugField(max_length=50, unique=True)),
                ('nombre', models.CharField(max_length=100)),
                ('descripcion', models.TextField(blank=True)),
                ('orden', models.PositiveIntegerField(default=0)),
                ('es_propio', models.BooleanField(default=False)),
                ('activo', models.BooleanField(default=True)),
                ('requiere_ot', models.BooleanField(default=False)),
            ],
            options={
                'verbose_name': 'Transporte configurable',
                'verbose_name_plural': 'Transportes configurables',
                'ordering': ['orden', 'nombre'],
                'db_table': 'config_transportes',
            },
        ),
    ]

