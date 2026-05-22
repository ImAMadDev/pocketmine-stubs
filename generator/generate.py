#!/usr/bin/env python3
"""
generate.py — PocketIDE / pocketmine-stubs
Punto de entrada CLI para generar stubs de PocketMine-MP.

Uso:
  python generate.py --version=5.42.1 [--workdir=./workdir] [--output=./output]

Produce:
  output/stubs-5.42.1.zip   → stubs comprimidos para publicar como GitHub Release
  output/stats-5.42.1.json  → estadísticas de la generación
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
        description="Genera stubs PHP de PocketMine-MP para PocketIDE / Intelephense"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Versión de PocketMine-MP a procesar (ej: 5.42.1)",
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

    merger = StubMerger(workdir=workdir, version=args.version)

    # Override para omitir phpstorm fork si se pide
    if args.skip_phpstorm:

        def run_without_phpstorm(output_zip: Path) -> str:
            import time

            t0 = time.time()
            phar = merger.download_phar()
            extracted = merger.extract_phar(phar)
            merger.parse_pocketmine(extracted)
            merger.generate_stubs()
            sha256 = merger.zip_stubs(output_zip)
            logger.info(f"🏁 Completado en {round(time.time() - t0, 1)}s")
            return sha256

        merger.run = run_without_phpstorm

    output_zip = output_dir / f"stubs-{args.version}.zip"

    logger.info(f"🚀 Generando stubs para PocketMine-MP {args.version}")
    logger.info(f"   workdir:    {workdir}")
    logger.info(f"   output zip: {output_zip}")

    try:
        sha256 = merger.run(output_zip)
        merger._write_stats(output_zip, sha256)

        # Imprimir SHA256 en stdout como última línea (lo captura GitHub Actions)
        print(sha256)
        logger.info(f"✅ SHA256: {sha256}")

    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
