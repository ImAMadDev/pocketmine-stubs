# pocketmine-stubs

Repositorio de soporte para **PocketIDE** — genera y publica los stubs PHP
de PocketMine-MP listos para consumir con **Intelephense** (autocompletado en VSCode/PhpStorm).

Los stubs se publican como [GitHub Releases](https://github.com/pocketide/pocketmine-stubs/releases)
por versión. El IDE los descarga según lo indicado en
[pocketide/pocketmine-manifest](https://github.com/pocketide/pocketmine-manifest).

---

## ¿Cómo se generan los stubs?

```
PocketMine-MP.phar
       │
       ▼
  [PHP subprocess]           phpstorm-stubs fork
  Extrae archivos .php    +  (pmmp/phpstorm-stubs)
       │                              │
       └──────────────┬───────────────┘
                      ▼
              PHPParser (Python/regex)
              Extrae firmas: clases,
              interfaces, traits, funciones,
              constantes — sin implementación
                      │
                      ▼
              StubMerger
              PM tiene prioridad sobre phpstorm-stubs
                      │
                      ▼
              Archivos .php por namespace
              + autocompletion_index.json
              + .phpstorm.meta.php
                      │
                      ▼
              stubs-X.Y.Z.zip  ← publicado como Release
```

**No se requieren dependencias Python externas.** El generador usa solo stdlib.
PHP 8.2+ es necesario solo para extraer el `.phar`.

> **Nota:** Los stubs incluyen métodos, propiedades y constantes **completas** con tipos y valores reales.

---

## Generar stubs para una versión nueva

### Vía GitHub Actions (recomendado)

```
Actions → "Generate Stubs" → version: 5.42.1 → Run workflow
```

En ~5 minutos aparece el Release con `stubs-5.42.1.zip` y su SHA256.

### Localmente

```bash
# Clonar el repo
git clone https://github.com/pocketide/pocketmine-stubs
cd pocketmine-stubs

# PHP 8.2+ y Python 3.11+ requeridos; sin dependencias extra
python3 generator/generate.py --version=5.42.1

# Con opciones
python3 generator/generate.py \
  --version=5.42.1 \
  --workdir=./mi_workdir \
  --output=./mi_output \
  --clean                     # limpia workdir antes de empezar

# Más rápido (sin phpstorm-stubs, solo PocketMine sources):
python3 generator/generate.py --version=5.42.1 --skip-phpstorm
```

**Output:**
- `output/stubs-5.42.1.zip` → stubs listos
- `output/stats-5.42.1.json` → estadísticas
- STDOUT: SHA256 del ZIP (para copiar a manifest.json)

---

## Opciones del generador

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--version=X.Y.Z` | *(requerido)* | Versión de PocketMine-MP |
| `--workdir=PATH` | `./workdir` | Dir temporal (descarga + extracción) |
| `--output=PATH` | `./output` | Dir de salida para ZIP y stats |
| `--clean` | `false` | Limpia workdir al inicio |
| `--skip-phpstorm` | `false` | Omite phpstorm-stubs fork (~50% más rápido) |

---

## Contenido del ZIP

```
stubs-5.42.1.zip
├── _global.php                    ← constantes y funciones globales
├── pocketmine/
│   └── stubs.php                  ← clases del namespace pocketmine
├── pocketmine/
│   ├── entity/stubs.php
│   ├── world/stubs.php
│   ├── network/mcpe/stubs.php
│   └── ...
├── .phpstorm.meta.php             ← metadata para PhpStorm
└── autocompletion_index.json      ← índice JSON para PocketIDE
```

### autocompletion_index.json

Consumido directamente por PocketIDE para autocompletado sin parsear PHP:

```json
{
  "version": "5.42.1",
  "namespaces": ["pocketmine", "pocketmine\\entity", "..."],
  "classes": {
    "Server": {
      "namespace": "pocketmine",
      "extends": null,
      "methods": ["getInstance", "broadcastMessage", "..."],
      "properties": ["..."],
      "constants": ["..."]
    }
  },
  "functions": { "...": {} },
  "constants":  { "...": {} }
}
```

---

## Arquitectura del generador

```
generator/
├── generate.py      ← CLI entry point (produce SHA256 en stdout)
├── merger.py        ← StubMerger: orquestador completo del pipeline
├── php_parser.py    ← PHPParser: regex-based, sin dependencias externas
└── requirements.txt ← vacío (solo stdlib)
```

### PHPParser (`php_parser.py`)

Parser PHP basado en expresiones regulares (sin dependencias externas). Extrae:
- `class`, `interface`, `trait`, `enum`
- Métodos con visibilidad, `static`, `abstract`, `final`, tipos de retorno y parámetros
- Propiedades con `readonly`, tipos, valores default y documentación
- Constantes de clase con visibilidad y valores reales
- Funciones globales con parámetros completos, constantes `define()`
- Namespaces y `use` statements
- Documentación PHPDoc preservada en stubs

### StubMerger (`merger.py`)

Orquestador del pipeline completo con fusión de fuentes:
- **PocketMine-MP** (prioridad alta): fuente de verdad para la API
- **phpstorm-stubs fork** (prioridad baja): complementa types de PHP builtin

Generación:
1. Descarga y extrae `PocketMine-MP.phar` con PHP
2. Parsea fuentes de PocketMine-MP con `PHPParser`
3. Parsea phpstorm-stubs fork (opcional con `--skip-phpstorm`)
4. Fusiona con prioridad a PocketMine-MP
5. Genera archivos `.php` por namespace
6. Crea `autocompletion_index.json` para PocketIDE
7. Comprime todo en `stubs-X.Y.Z.zip`

---

## Ecosistema PocketIDE

| Repositorio | Propósito |
|-------------|-----------|
| [`pocketide/pocketide`](https://github.com/pocketide/pocketide) | IDE principal (Tauri 2 + React 19) |
| [`pocketide/pocketmine-manifest`](https://github.com/pocketide/pocketmine-manifest) | Manifest de versiones disponibles |
| [`pocketide/pocketmine-stubs`](https://github.com/pocketide/pocketmine-stubs) | **Este repositorio** |

---

*PocketIDE Ecosystem — pocketide/pocketmine-stubs*

---

## Desarrollo

### Estructura del proyecto

```
pocketmine-stubs/
├── README.md                  ← Este archivo
├── .gitignore                 ← Archivos a ignorar en git
├── generator/
│   ├── __init__.py
│   └── generate.py            ← Punto de entrada CLI
├── merger/
│   └── merger.py              ← Orquestador del pipeline
├── php_parser.py              ← Parser PHP sin dependencias
├── requirements.txt           ← Dependencias (vacío)
└── .github/
    └── workflows/
        └── generate.yml       ← GitHub Actions para generar stubs
```

### Testing local

```bash
# Generar stubs para versión 5.43.1
python3 generator/generate.py --version=5.43.1

# Con limpieza
python3 generator/generate.py --version=5.43.1 --clean

# Verificar output
ls -lh output/stubs-*.zip
unzip -l output/stubs-5.43.1.zip | head -20
```

### Debugging

El generador proporciona información detallada en stderr:

```bash
# Ver logs mientras se ejecuta
python3 generator/generate.py --version=5.43.1 2>&1 | tail -30
```

Tiempo promedio de generación: ~2 minutos (con descarga de phpstorm-stubs).

---
