import sys

path = r'd:\informatica\python\sistemaPesco\README.MD'
# Try different encodings
encodings = ['utf-8', 'latin-1', 'windows-1252']
content = None

for enc in encodings:
    try:
        with open(path, 'r', encoding=enc) as f:
            content = f.read()
            print(f"Read successful with {enc}")
            break
    except Exception:
        continue

if content is None:
    print("Could not read README.MD")
    sys.exit(1)

# Update Fase 3 and 5 items (using partial match since accents might differ)
content = content.replace('Desarrollar m', 'Desarrollar m') # Generic match
# Let's just append the changelog at the top or specific place

new_changelog = """
### Versión 4.0 (Mayo 2026) - Sistema de Embalaje Parcial y Lotes (Crossdocking)
- ✅ **Embalaje Parcial (Fraccionamiento):** Permite separar unidades de un mismo código en bultos distintos.
- ✅ **Creación Múltiple (Modo Lote):** Algoritmo de "Regla del Resto" para dividir grandes cantidades automáticamente.
- ✅ **Clonado de Medidas:** Copia automática de peso y dimensiones a todos los bultos del lote.
- ✅ **Impresión en Lote:** Vista de impresión continua para etiquetas térmicas (10x14cm).
- ✅ **Seguridad por Roles:** Campos de transporte exclusivos para Administradores.
- ✅ **Validaciones Robustas:** Medidas obligatorias en lotes y bloqueo de pedidos completados.
- ✅ **Optimización JSON:** Fix para números Decimales en etiquetas masivas.

"""

if '### Versión 3.0' in content:
    content = content.replace('### Versión 3.0', new_changelog + '### Versión 3.0')
else:
    content += new_changelog

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("README.MD updated successfully.")
