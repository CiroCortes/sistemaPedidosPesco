from django.core.management.base import BaseCommand
from configuracion.models import TipoSolicitud


class Command(BaseCommand):
    help = 'Pobla la tabla de tipos de solicitud con los tipos iniciales'

    def handle(self, *args, **options):
        tipos_iniciales = [
            ('PC', 'PC', 'Pedido Cliente', 10, 'file-text', 'primary'),
            ('OC', 'OC', 'Orden de Compra', 20, 'file-earmark-text', 'info'),
            ('EM', 'Emergencia', 'Solicitud de Emergencia', 30, 'exclamation-triangle', 'danger'),
            ('ST', 'Solicitud de Traslado', 'Solicitud de Traslado Interno', 40, 'arrow-right-circle', 'success'),
            ('OF', 'Oficina', 'Pedido de Oficina', 50, 'briefcase', 'secondary'),
            ('RM', 'Retiro de Mercancías', 'Retiro de Mercancías por Cliente', 60, 'box-arrow-right', 'warning'),
        ]
        
        creados = 0
        actualizados = 0
        
        for codigo, nombre, descripcion, orden, icono, color in tipos_iniciales:
            tipo, created = TipoSolicitud.objects.update_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre,
                    'descripcion': descripcion,
                    'orden': orden,
                    'icono': icono,
                    'color': color,
                    'activo': True,
                },
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Creado: {codigo} - {nombre}'))
                creados += 1
            else:
                self.stdout.write(self.style.WARNING(f'Actualizado: {codigo} - {nombre}'))
                actualizados += 1
        
        # Limpiar caché
        TipoSolicitud.limpiar_cache()
        
        self.stdout.write(self.style.SUCCESS(f'\nProceso completado:'))
        self.stdout.write(self.style.SUCCESS(f'   Creados: {creados}'))
        self.stdout.write(self.style.SUCCESS(f'   Actualizados: {actualizados}'))
        self.stdout.write(self.style.SUCCESS(f'   Total: {TipoSolicitud.objects.count()}'))

