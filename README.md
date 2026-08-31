# pocketmine-stubs

Repositorio de soporte para **Deepslate** — genera y publica los stubs PHP
de **PocketMine-MP y cualquier fork** listos para consumir con **Intelephense** (autocompletado en VSCode/PhpStorm/Deepslate).

Los stubs se publican como [GitHub Releases](https://github.com/ImAMadDev/pocketmine-stubs/releases)
por versión y software. El IDE los descarga según lo indicado en
[ImAMadDev/pocketmine-manifest](https://github.com/ImAMadDev/pocketmine-manifest).

---

## ¿Cómo se generan los stubs?

```
 PocketMine-MP / Altay / Cualquier Fork (PHAR, ZIP o local)
                       │
                       ▼
                 [StubMerger]           phpstorm-stubs fork
           Extrae archivos .php      +  (pmmp/phpstorm-stubs)
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
                              Servidor tiene prioridad sobre phpstorm-stubs
                                      │
                                      ▼
                              Archivos .php por namespace
                              + autocompletion_index.json
                              + .phpstorm.meta.php
                                      │
                                      ▼
                              stubs-[software-]X.Y.Z.zip  ← publicado como Release
```

**No se requieren dependencias Python externas.** El generador usa solo la librería estándar de Python.
PHP 8.2+ es necesario solo para extraer archivos `.phar`.

> **Nota:** Los stubs incluyen métodos, propiedades y constantes **completas** con tipos y valores reales.

---

## Soporte Universal de Forks (`forks.json`)

El repositorio incluye un archivo central [`forks.json`](file:///home/luq/Github%20Projects/pocketmine-stubs/forks.json) que define los forks conocidos, sus repositorios, assets PHAR o fuentes ZIP:

```json
{
  "forks": {
    "pocketmine": {
      "name": "PocketMine-MP",
      "repo": "pmmp/PocketMine-MP",
      "type": "phar",
      "phar_url_template": "https://github.com/pmmp/PocketMine-MP/releases/download/{version}/PocketMine-MP.phar",
      "phar_latest_url": "https://github.com/pmmp/PocketMine-MP/releases/latest/download/PocketMine-MP.phar",
      "source_url_template": "https://github.com/pmmp/PocketMine-MP/archive/refs/tags/{version}.zip",
      "phar_name": "PocketMine-MP.phar",
      "tag_prefix": "",
      "release_name_template": "Stubs PocketMine-MP {version}"
    },
    "altay": {
      "name": "Altay",
      "repo": "altayofficial/Altay",
      "type": "phar",
      "phar_url_template": "https://github.com/altayofficial/Altay/releases/download/{version}/Altay.phar",
      "phar_latest_url": "https://github.com/altayofficial/Altay/releases/latest/download/Altay.phar",
      "source_url_template": "https://github.com/altayofficial/Altay/archive/refs/tags/{version}.zip",
      "phar_name": "Altay.phar",
      "tag_prefix": "altay-",
      "release_name_template": "Stubs Altay {version}"
    }
  }
}
```

Cualquier persona puede agregar nuevos forks a `forks.json` mediante un Pull Request.

---

## Generar stubs para una versión nueva

### Vía GitHub Actions (recomendado)

1. Ve a **Actions** → **"Generate Stubs"** → **Run workflow**.
2. Parámetros disponibles:
   - `version`: Versión o tag (ej: `5.42.1` o `5.44.4`).
   - `software`: Identificador de fork (ej: `pocketmine`, `altay`, `prismarine` o custom).
   - `repo`: Repositorio GitHub opcional en formato `owner/repo`.
   - `phar_url` / `source_url`: URLs directas personalizadas (opcional).
   - `skip_phpstorm`: Omitir phpstorm-stubs fork (más rápido).

En pocos minutos aparece el Release con `stubs-[software-]X.Y.Z.zip` y su SHA256.

### Localmente

```bash
# PocketMine-MP estándar
python3 generator/generate.py --version=5.42.1

# Fork preconfigurado en forks.json (ej: Altay)
python3 generator/generate.py --software=altay --version=5.44.4

# Fork de GitHub ad-hoc (descarga release asset automáticamente)
python3 generator/generate.py --software=myfork --repo=owner/repo --version=1.0.0

# Fork desde URL directa (PHAR o código fuente en ZIP)
python3 generator/generate.py --software=myfork --version=1.0.0 --phar-url="https://example.com/custom.phar"

# Fork desde directorio o archivo local
python3 generator/generate.py --software=myfork --version=1.0.0 --source-path="/ruta/a/fuentes_php"

# Opciones adicionales
python3 generator/generate.py --version=5.42.1 --clean --skip-phpstorm
```

**Output:**
- `output/stubs-[software-]X.Y.Z.zip` → stubs listos
- `output/stats-[software-]X.Y.Z.json` → estadísticas
- STDOUT: SHA256 del ZIP (para copiar a manifest.json)

---

## Opciones del generador CLI

| Opción | Default | Descripción |
|--------|---------|-------------|
| `--version=X.Y.Z` | *(requerido)* | Versión del software / tag |
| `--software=NAME` | `pocketmine` | Identificador del fork / software |
| `--repo=OWNER/REPO` | `None` | Repositorio GitHub de origen |
| `--phar-url=URL` | `None` | URL directa o plantilla del archivo `.phar` |
| `--source-url=URL` | `None` | URL directa o plantilla del `.zip` de código fuente |
| `--source-path=PATH` | `None` | Ruta local a `.phar`, `.zip` o directorio fuente |
| `--phar-name=NAME` | `None` | Nombre del binario PHAR (ej: `Altay.phar`) |
| `--forks-file=PATH` | `forks.json` | Ruta personalizada al archivo de configuración |
| `--workdir=PATH` | `./workdir` | Directorio temporal |
| `--output=PATH` | `./output` | Directorio de salida para ZIP y stats |
| `--clean` | `false` | Limpia workdir al inicio |
| `--skip-phpstorm` | `false` | Omite phpstorm-stubs fork (~50% más rápido) |

---

## Contenido del ZIP

```
stubs-[software-]X.Y.Z.zip
├── _global.php                    ← constantes y funciones globales
├── pocketmine/
│   └── Server.php                 ← clases PHP con firmas completas
├── pocketmine/
│   ├── entity/
│   ├── world/
│   └── ...
├── .phpstorm.meta.php             ← metadata para PhpStorm / Intelephense
└── autocompletion_index.json      ← índice JSON para Deepslate
```

---

## Ecosistema Deepslate

| Repositorio | Propósito |
|-------------|-----------|
| [`ImAMadDev/deepslate`](https://github.com/ImAMadDev/deepslate) | IDE principal (Tauri 2 + React 19) |
| [`ImAMadDev/pocketmine-manifest`](https://github.com/ImAMadDev/pocketmine-manifest) | Manifest de versiones disponibles |
| [`ImAMadDev/pocketmine-stubs`](https://github.com/ImAMadDev/pocketmine-stubs) | **Este repositorio** |

---

*Deepslate Ecosystem — ImAMadDev/pocketmine-stubs*
