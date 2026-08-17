#!/usr/bin/env python3
"""
ejemplo_gui_avanzada.py — Ejemplos de uso de la GUI avanzada.

Demuestra cómo:
1. Cargar un reporte JSON
2. Filtrar grupos programáticamente
3. Seleccionar archivos para eliminar
4. Ejecutar la GUI con datos precargados

Uso:
    python ejemplo_gui_avanzada.py                    # GUI interactiva vacía
    python ejemplo_gui_avanzada.py reporte.json       # Pre-carga reporte
    python ejemplo_gui_avanzada.py reporte.json 95    # Pre-carga + filtro 95%
"""

import argparse
import json
import sys
from pathlib import Path

# Importar la GUI avanzada
try:
    from media_dedupe_gui_advance import VentanaAvanzada
except ImportError:
    print("❌ Error: no se pudo importar media_dedupe_gui_advance.py")
    print("Asegúrate de que media_dedupe_gui_advance.py está en el mismo directorio")
    sys.exit(1)


def ejemplo_1_gui_básica():
    """
    Ejemplo 1: Abrir la GUI sin datos precargados.
    
    El usuario debe hacer clic en "📂 Abrir Reporte..." para cargar un JSON.
    """
    print("\n📖 EJEMPLO 1: GUI Básica")
    print("─" * 50)
    print("Abriendo GUI sin datos...")
    print("Pasos:")
    print("  1. Clic en '📂 Abrir Reporte...'")
    print("  2. Selecciona un reporte.json")
    print("  3. Filtra y selecciona archivos")
    print("  4. Elimina seleccionadas\n")
    
    app = VentanaAvanzada()
    app.mainloop()


def ejemplo_2_gui_con_reporte(ruta_reporte: str, umbral: int = None):
    """
    Ejemplo 2: Abrir la GUI con un reporte precargado.
    
    Args:
        ruta_reporte: Ruta al archivo reporte.json
        umbral: (Opcional) Umbral de filtro inicial (0-100)
    """
    print("\n📖 EJEMPLO 2: GUI con Reporte Precargado")
    print("─" * 50)
    print(f"Cargando reporte: {ruta_reporte}")
    
    app = VentanaAvanzada()
    
    # Pre-cargar el reporte
    try:
        app._cargar_reporte_json(ruta_reporte)
        print(f"✓ Reporte cargado: {len(app.datos_originales)} grupos")
    except Exception as e:
        print(f"❌ Error al cargar: {e}")
        return
    
    # Aplicar filtro si se especifica
    if umbral is not None:
        print(f"Aplicando filtro: {umbral}%")
        app._aplicar_filtro(umbral)
        print(f"Grupos filtrados: {len(app.datos_filtrados)}")
    
    app.mainloop()


def ejemplo_3_análisis_reporte(ruta_reporte: str):
    """
    Ejemplo 3: Analizar un reporte sin abrir GUI.
    
    Útil para estadísticas y decisiones automatizadas.
    """
    print("\n📖 EJEMPLO 3: Análisis de Reporte (sin GUI)")
    print("─" * 50)
    
    try:
        with open(ruta_reporte, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    grupos = datos.get("groups", [])
    
    print(f"\n📊 ESTADÍSTICAS GENERALES")
    print(f"  Total de grupos: {len(grupos)}")
    print(f"  Espacio recuperable: {datos.get('total_recoverable_size', 0) / 1024**2:.1f} MB")
    print(f"  Fecha de escaneo: {datos.get('generated_at', 'N/A')}")
    
    # Desglose por tipo
    print(f"\n📁 DESGLOSE POR TIPO")
    tipos = {}
    for grupo in grupos:
        tipo = grupo.get("group_type", "desconocido")
        if tipo not in tipos:
            tipos[tipo] = {"count": 0, "size": 0, "archivos": 0}
        tipos[tipo]["count"] += 1
        tipos[tipo]["size"] += grupo.get("recoverable_size", 0)
        tipos[tipo]["archivos"] += len(grupo.get("files", []))
    
    for tipo, stats in tipos.items():
        print(f"  {tipo:20s}: {stats['count']:3d} grupos | "
              f"{stats['archivos']:3d} archivos | "
              f"{stats['size']/1024**2:6.1f} MB")
    
    # Grupos más grandes
    print(f"\n🔝 TOP 5 GRUPOS MÁS GRANDES")
    grupos_ordenados = sorted(
        grupos,
        key=lambda g: g.get("recoverable_size", 0),
        reverse=True
    )
    
    for i, grupo in enumerate(grupos_ordenados[:5], 1):
        tamaño = grupo.get("recoverable_size", 0) / 1024**2
        score = grupo.get("score", 100)
        tipo = grupo.get("group_type", "?")
        archivos = len(grupo.get("files", []))
        print(f"  {i}. {tipo:15s} | {tamaño:6.1f} MB | {score:5.1f}% | {archivos} archivos")
    
    # Simulación de eliminación segura
    print(f"\n🔒 SIMULACIÓN DE ELIMINACIÓN SEGURA")
    eliminables = 0
    no_eliminables = 0
    
    for grupo in grupos:
        archivos = grupo.get("files", [])
        for archivo in archivos[1:]:  # Todos excepto el primero (mejor)
            ruta = archivo.get("path")
            if ruta and ruta.startswith("C:\\"):  # Archivo local
                eliminables += 1
            else:
                no_eliminables += 1
    
    print(f"  Archivos locales (eliminables): {eliminables}")
    print(f"  Archivos cloud (protegidos): {no_eliminables}")


def ejemplo_4_buscar_exactos(ruta_reporte: str):
    """
    Ejemplo 4: Buscar solo duplicados exactos y mostrar su ubicación.
    """
    print("\n📖 EJEMPLO 4: Buscar Duplicados Exactos")
    print("─" * 50)
    
    try:
        with open(ruta_reporte, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    grupos = datos.get("groups", [])
    exactos = [g for g in grupos if g.get("group_type") == "exact"]
    
    print(f"Encontrados {len(exactos)} grupo(s) de duplicados exactos:\n")
    
    for i, grupo in enumerate(exactos, 1):
        archivos = grupo.get("files", [])
        espacio = grupo.get("recoverable_size", 0) / 1024**2
        
        print(f"Grupo {i}: {len(archivos)} archivos ({espacio:.1f} MB)")
        
        for j, archivo in enumerate(archivos):
            marca = "⭐" if j == 0 else "  "
            nombre = archivo.get("name", "sin nombre")
            tamaño = archivo.get("size", 0) / 1024**2
            origen = archivo.get("source", "?")
            ruta = archivo.get("path", archivo.get("web_url", "N/A"))
            
            print(f"  {marca} [{j+1}] {nombre} ({tamaño:.1f} MB)")
            print(f"       Origen: {origen}")
            print(f"       Ruta: {ruta[:60]}...")
        print()


def ejemplo_5_filtrar_y_reportar(ruta_reporte: str, umbral: float):
    """
    Ejemplo 5: Filtrar por umbral y generar reporte de lo que se eliminaría.
    """
    print("\n📖 EJEMPLO 5: Filtrar y Reportar (sin eliminar)")
    print("─" * 50)
    print(f"Filtro: similitud >= {umbral}%\n")
    
    try:
        with open(ruta_reporte, "r", encoding="utf-8") as f:
            datos = json.load(f)
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    grupos = datos.get("groups", [])
    filtrados = [g for g in grupos if g.get("score", 100) >= umbral]
    
    total_size_antes = sum(g.get("recoverable_size", 0) for g in grupos)
    total_size_filtrado = sum(g.get("recoverable_size", 0) for g in filtrados)
    
    print(f"📊 RESULTADOS DEL FILTRO")
    print(f"  Grupos originales: {len(grupos)}")
    print(f"  Grupos filtrados:  {len(filtrados)} ({100*len(filtrados)/len(grupos):.1f}%)")
    print(f"  Espacio total:     {total_size_antes/1024**2:.1f} MB")
    print(f"  Espacio filtrado:  {total_size_filtrado/1024**2:.1f} MB")
    
    if filtrados:
        print(f"\n📋 ARCHIVOS A ELIMINAR")
        
        total_archivos = 0
        total_size = 0
        
        for grupo in filtrados:
            archivos = grupo.get("files", [])
            # El primero es el "mejor", los demás se marcarían
            for archivo in archivos[1:]:
                total_archivos += 1
                tamaño = archivo.get("size", 0)
                total_size += tamaño
                
                nombre = archivo.get("name", "sin nombre")
                tamaño_mb = tamaño / 1024**2
                ruta = archivo.get("path", "cloud")
                
                # Solo mostrar si es local
                if ruta and not ruta.startswith("http"):
                    print(f"  - {nombre} ({tamaño_mb:.1f} MB)")
                    print(f"    {ruta}")
        
        print(f"\n✓ RESUMEN")
        print(f"  Archivos a eliminar: {total_archivos}")
        print(f"  Espacio liberado: {total_size/1024**2:.1f} MB")


def main():
    """Función principal con argumentos CLI."""
    parser = argparse.ArgumentParser(
        description="Ejemplos de uso de la GUI avanzada de Media Dedupe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:

  # GUI sin datos
  python ejemplo_gui_avanzada.py

  # GUI con reporte precargado
  python ejemplo_gui_avanzada.py reporte.json

  # GUI con reporte y filtro inicial
  python ejemplo_gui_avanzada.py reporte.json --filter 95

  # Análisis sin GUI
  python ejemplo_gui_avanzada.py reporte.json --analyze

  # Buscar solo exactos
  python ejemplo_gui_avanzada.py reporte.json --exact

  # Filtrar y reportar
  python ejemplo_gui_avanzada.py reporte.json --filter-report 95
        """
    )
    
    parser.add_argument(
        "reporte",
        nargs="?",
        help="Ruta al archivo reporte.json"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Analizar reporte sin abrir GUI"
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Mostrar solo duplicados exactos"
    )
    parser.add_argument(
        "--filter",
        type=int,
        metavar="N",
        help="Abrir GUI con filtro inicial (0-100)"
    )
    parser.add_argument(
        "--filter-report",
        type=float,
        metavar="N",
        help="Reportar qué se eliminaría con filtro N (sin GUI)"
    )
    
    args = parser.parse_args()
    
    # Caso 1: Sin argumentos → GUI básica
    if not args.reporte:
        ejemplo_1_gui_básica()
    
    # Caso 2: Reporte existe
    elif Path(args.reporte).exists():
        # Sub-casos
        if args.analyze:
            ejemplo_3_análisis_reporte(args.reporte)
        elif args.exact:
            ejemplo_4_buscar_exactos(args.reporte)
        elif args.filter_report is not None:
            ejemplo_5_filtrar_y_reportar(args.reporte, args.filter_report)
        else:
            # GUI con reporte (y filtro opcional)
            ejemplo_2_gui_con_reporte(args.reporte, args.filter)
    else:
        print(f"❌ No existe: {args.reporte}")
        sys.exit(1)


if __name__ == "__main__":
    main()
