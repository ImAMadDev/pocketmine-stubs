#!/usr/bin/env python3
"""
generate.py — Deepslate / pocketmine-stubs
Punto de entrada CLI para generar stubs de PocketMine-MP y cualquier fork.

Uso:
  python generate.py --version=5.42.1 [--software=pocketmine] [--workdir=./workdir] [--output=./output]
  python generate.py --software=altay --version=1.0.0
  python generate.py --software=custom --repo=owner/repo --version=1.0.0
  python generate.py --software=custom --source-path=/path/to/server/src --version=1.0.0

Produce:
  output/stubs-[software-]X.Y.Z.zip   → stubs comprimidos para publicar como GitHub Release
  output/stats-[software-]X.Y.Z.json  → estadísticas de la generación
  STDOUT: SHA256 del ZIP en la última línea (usado por GitHub Actions)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Agregar el directorio del script al path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))
# Agregar el directorio padre para importar módulos de hermanos
sys.path.insert(0, str(Path(__file__).parent.parent))

from merger.merger import StubMerger  # noqa: E402

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,  # stderr para no contaminar el SHA256 en stdout
)
logger = logging.getLogger(__name__)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera stubs PHP de PocketMine-MP y sus forks para Deepslate / Intelephense"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Versión del software a procesar (ej: 5.42.1 o 1.0.0)",
    )
    parser.add_argument(
        "--software",
        default="pocketmine",
        help="Nombre/identificador del fork o servidor (default: pocketmine, ej: altay, prismarine)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Repositorio GitHub en formato owner/repo (ej: altayofficial/Altay)",
    )
    parser.add_argument(
        "--phar-url",
        default=None,
        help="URL directa o plantilla de descarga del archivo .phar (soporta {version})",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help="URL directa o plantilla de descarga de código fuente en .zip (soporta {version})",
    )
    parser.add_argument(
        "--source-path",
        default=None,
        help="Ruta local a un archivo .phar, .zip o directorio fuente",
    )
    parser.add_argument(
        "--phar-name",
        default=None,
        help="Nombre del archivo PHAR esperado en releases (ej: PocketMine-MP.phar o Altay.phar)",
    )
    parser.add_argument(
        "--forks-file",
        default=None,
        help="Ruta personalizada al archivo de configuración forks.json",
    )
    parser.add_argument(
        "--workdir",
        default="./workdir",
        help="Directorio de trabajo temporal (default: ./workdir)",
    )
    parser.add_argument(
        "--output",
        default="./output",
        help="Directorio de salida para el ZIP (default: ./output)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Limpiar workdir antes de empezar",
    )
    parser.add_argument(
        "--skip-phpstorm",
        action="store_true",
        help="Omitir descarga de phpstorm-stubs fork (más rápido, menos completo)",
    )
    return parser.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()

    workdir = Path(args.workdir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clean and workdir.exists():
        import shutil

        logger.info(f"🧹 Limpiando workdir {workdir}")
        shutil.rmtree(workdir)

    merger = StubMerger(
        workdir=workdir,
        version=args.version,
        software=args.software,
        repo=args.repo,
        phar_url=args.phar_url,
        source_url=args.source_url,
        source_path=args.source_path,
        phar_name=args.phar_name,
        forks_file=args.forks_file,
    )

    # Override para omitir phpstorm fork si se pide
    if args.skip_phpstorm:

        def run_without_phpstorm(output_zip: Path) -> str:
            import time

            t0 = time.time()
            extracted = merger.acquire_and_extract_source()
            merger.parse_server(extracted)
            merger.generate_stubs()
            sha256 = merger.zip_stubs(output_zip)
            logger.info(f"🏁 Completado en {round(time.time() - t0, 1)}s")
            return sha256

        merger.run = run_without_phpstorm

    software_clean = args.software.lower().strip()
    zip_prefix = f"stubs-{software_clean}" if software_clean != "pocketmine" else "stubs"
    output_zip = output_dir / f"{zip_prefix}-{args.version}.zip"

    logger.info(f"🚀 Generando stubs para {merger.software_display_name} {args.version}")
    logger.info(f"   workdir:    {workdir}")
    logger.info(f"   output zip: {output_zip}")

    try:
        sha256 = merger.run(output_zip)
        merger._write_stats(output_zip, sha256)

        # Validar que SHA256 sea válido (64 caracteres hex)
        if not sha256 or len(sha256.strip()) != 64:
            logger.error(f"❌ SHA256 inválido: {sha256}")
            sys.exit(1)

        # Imprimir SHA256 en stdout como última línea (lo captura GitHub Actions)
        print(sha256.strip())
        logger.info(f"✅ SHA256: {sha256}")

    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
