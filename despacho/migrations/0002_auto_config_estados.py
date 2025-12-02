from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('despacho', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bulto',
            name='estado',
            field=models.CharField(default='pendiente', max_length=30),
        ),
        migrations.AlterField(
            model_name='bulto',
            name='transportista',
            field=models.CharField(default='PESCO', max_length=50),
        ),
    ]

