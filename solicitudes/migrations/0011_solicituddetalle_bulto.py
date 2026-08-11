from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('despacho', '0001_initial'),
        ('solicitudes', '0010_alter_solicitud_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='solicituddetalle',
            name='bulto',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='detalles', to='despacho.bulto', verbose_name='Bulto asignado'),
        ),
    ]

