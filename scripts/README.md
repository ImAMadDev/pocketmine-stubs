# Scripts de Generación en Batch

Este directorio contiene herramientas para obtener los releases de PocketMine-MP y determinar cuáles no se han generado para este repositorio de stubs.

## Flujo General

El script `batch_generate.py` ahora unifica todo el flujo de trabajo:

```
1. Consulta GitHub Releases de PocketMine-MP.
2. Filtra los candidatos conservando el patch más reciente de cada minor version (X.Y).
3. Obtiene las versiones ya generadas (escaneando localmente el directorio output/ y consultando GitHub Releases).
4. Determina las versiones pendientes.
5. Ordena las pendientes de menor a mayor.
6. [Opcional] Con --print-pending, imprime los tags de las versiones pendientes a stdout y termina.
7. [Por defecto] Valida build_info.json de cada versión pendiente y genera los stubs.
```

---

## 1. batch_generate.py

**Propósito:** Buscar releases de PocketMine-MP y generar stubs para las versiones que falten (u obtener la lista en texto plano).

### Uso Básico

```bash
# Generar todas las versiones pendientes localmente
python3 scripts/batch_generate.py

# Listar únicamente las versiones pendientes a stdout (útil para integraciones)
python3 scripts/batch_generate.py --print-pending
```

### Opciones

```bash
# Límite de versiones a procesar
python3 scripts/batch_generate.py --limit=3

# Incluir pre-releases (por defecto se excluyen)
python3 scripts/batch_generate.py --include-prereleases

# Omitir descarga de phpstorm-stubs (más rápido, menos completo)
python3 scripts/batch_generate.py --skip-phpstorm

# No limpiar workdir entre generaciones
python3 scripts/batch_generate.py --no-clean

# Dry-run (mostrar qué se generaría sin ejecutar la generación real)
python3 scripts/batch_generate.py --dry-run

# Mostrar solo versiones ya generadas
python3 scripts/batch_generate.py --generated-only

# Con token de GitHub (aumenta rate limit para APIs)
python3 scripts/batch_generate.py --token=ghp_xxx...

# Especificar repositorio de stubs destino manualmente
python3 scripts/batch_generate.py --repo=pocketide/pocketmine-stubs
```

---

## 2. Workflow de GitHub Actions (`batch-generate.yml`)

El workflow `.github/workflows/batch-generate.yml` sirve como despachador. Se ejecuta automáticamente cada 12 horas o de forma manual, y realiza los siguientes pasos:

1. Ejecuta `batch_generate.py --print-pending` para obtener el listado de versiones faltantes.
2. Para cada una de esas versiones, despacha una ejecución del workflow independiente **Generate Stubs** (`generate.yml`) pasándole los parámetros correspondientes.

Este diseño permite que cada versión se compile y publique en su propio workflow aislado e independiente, manteniendo un historial y control limpios.

---

## 3. Licencia y Créditos

Parte del ecosistema de [PocketIDE](https://github.com/pocketide).
