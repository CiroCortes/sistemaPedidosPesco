# dms_supplychain (dms-platform)

Placeholder inicial de Django para validar el despliegue en App Runner
(VPC, RDS, S3+CloudFront, Secrets Manager, Bedrock) vía Terraform.

Sin base de datos real conectada todavía (usa SQLite local como placeholder).
Cuando el desarrollador tenga el código definitivo, reemplaza este contenido
y actualiza `DATABASES` en `dms_platform/settings.py` para usar las
credenciales de RDS que entrega Secrets Manager.

## Desarrollo local

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

## Endpoints

- `GET /` y `GET /health/` — health check, responde `{"status": "ok"}`.
