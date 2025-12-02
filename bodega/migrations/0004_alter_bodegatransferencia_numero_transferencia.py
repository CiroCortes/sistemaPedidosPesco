from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bodega', '0003_rename_bodega_transfer_numero_bodega_tran_numero__724cbe_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bodegatransferencia',
            name='numero_transferencia',
            field=models.CharField(max_length=50),
        ),
    ]

