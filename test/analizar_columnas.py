import pandas as pd

# Leer el archivo Excel
file = 'test/DESPACHOS_ANALISIS.xlsx'

# Primero listar todas las hojas
xl = pd.ExcelFile(file)

# Buscar la hoja que contenga "2025"
hoja_objetivo = None
for sheet in xl.sheet_names:
    if '2025' in sheet.upper():
        hoja_objetivo = sheet
        break

if hoja_objetivo:
    # Leer solo las primeras filas para ver las columnas
    df = pd.read_excel(file, sheet_name=hoja_objetivo, nrows=5)
    
    # Guardar el análisis en un archivo
    with open('test/analisis_columnas_resultado.txt', 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write(f"ANÁLISIS DE COLUMNAS - HOJA: '{hoja_objetivo}'\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total de columnas: {len(df.columns)}\n\n")
        f.write("LISTA DE COLUMNAS:\n")
        f.write("-" * 80 + "\n")
        
        for i, col in enumerate(df.columns, 1):
            f.write(f"{i:2d}. {col}\n")
        
        f.write("\n" + "=" * 80 + "\n")
        f.write("PRIMERAS 5 FILAS (muestra de datos):\n")
        f.write("=" * 80 + "\n")
        f.write(df.to_string() + "\n")
    
    print(f"✅ Análisis guardado en: test/analisis_columnas_resultado.txt")
    print(f"Hoja analizada: '{hoja_objetivo}'")
    print(f"Total de columnas: {len(df.columns)}")
else:
    print("⚠️ No se encontró ninguna hoja con '2025' en el nombre")
