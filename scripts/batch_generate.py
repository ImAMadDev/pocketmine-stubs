#!/usr/bin/env python3
"""
batch_generate.py — Genera stubs para múltiples versiones de PocketMine-MP y sus forks

Descarga la lista de releases desde GitHub, filtra candidatos por minor versión,
verifica cuáles ya han sido generados (comprobando archivos locales y releases de GitHub),
y genera stubs para las versiones pendientes de menor a mayor.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ─── Constantes ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
GENERATOR_SCRIPT = PROJECT_ROOT / "generator" / "generate.py"
FORKS_FILE = PROJECT_ROOT / "forks.json"
REQUIRED_FIELDS = ("details_url", "download_url", "source_url", "php_download_url")


# ─── Fork Config Helper ───────────────────────────────────────────────────────

def load_fork_config(software: str, custom_forks_file: Path | None = None) -> dict[str, Any]:
    forks_path = custom_forks_file or FORKS_FILE
    forks_data: dict[str, Any] = {}
    if forks_path.exists():
        try:
            forks_data = json.loads(forks_path.read_text(encoding="utf-8")).get("forks", {})
        except Exception as e:
            logger.warning("⚠ Error leyendo forks.json: %s", e)

    cfg = forks_data.get(software.lower().strip(), {})
    name = cfg.get("name", software.capitalize())
    repo = cfg.get("repo", "pmmp/PocketMine-MP" if software == "pocketmine" else "")
    tag_prefix = cfg.get("tag_prefix", "" if software == "pocketmine" else f"{software}-")
    return {
        "software": software.lower().strip(),
        "name": name,
        "repo": repo,
        "tag_prefix": tag_prefix,
        "type": cfg.get("type", "phar"),
    }


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

def _get_token(cli_token: str | None = None) -> str | None:
    """Lee el token de GitHub desde el argumento CLI o de entorno."""
    return cli_token or os.getenv("GITHUB_TOKEN")


def fetch_json(url: str, token: str | None = None) -> Any:
    """Descarga y parsea JSON desde una URL."""
    headers: dict[str, str] = {"User-Agent": "pocketmine-stubs-batch/2.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error("HTTP %d: %s", e.code, url)
        raise
    except urllib.error.URLError as e:
        logger.error("URL error (%s): %s", e.reason, url)
        raise


# ─── GitHub / Git Helpers ─────────────────────────────────────────────────────

def fetch_all_releases(repo_slug: str, token: str | None) -> list[dict[str, Any]]:
    """Descarga todos los releases del repositorio paginando la API de GitHub."""
    releases: list[dict[str, Any]] = []
    page = 1

    while True:
        url = f"https://api.github.com/repos/{repo_slug}/releases?per_page=100&page={page}"
        logger.info("📥 Descargando releases de %s — página %d...", repo_slug, page)
        try:
            batch: list[dict[str, Any]] = fetch_json(url, token)
        except Exception as e:
            logger.error("❌ Falló la descarga de releases de %s: %s", repo_slug, e)
            break

        if not batch:
            break

        releases.extend(batch)
        logger.info("   → %d releases (total acumulado: %d)", len(batch), len(releases))

        if len(batch) < 100:  # Última página
            break

        page += 1

    return releases


def fetch_build_info(tag: str, repo: str, token: str | None) -> dict[str, Any] | None:
    """Descarga build_info.json desde los release assets de GitHub si existe."""
    url = f"https://github.com/{repo}/releases/download/{tag}/build_info.json"
    try:
        return fetch_json(url, token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            logger.debug("  ✗ build_info.json no encontrado para %s", tag)
        else:
            logger.debug(
                "  ✗ HTTP %d al descargar build_info.json para %s", e.code, tag
            )
        return None
    except Exception as e:
        logger.debug("  ✗ Error al descargar build_info.json para %s: %s", tag, e)
        return None


def get_repo_slug_from_git() -> str | None:
    """Intenta extraer owner/repo de la URL del remote origin."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()
        if "github.com" in url:
            parts = url.split("github.com")[-1].strip("/:").replace(".git", "")
            return parts
    except Exception:
        pass
    return None


def get_repo_slug(args_repo: str | None) -> str | None:
    """Obtiene el slug del repositorio de stubs actual."""
    if args_repo:
        return args_repo
    env_repo = os.getenv("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo
    return get_repo_slug_from_git()


def get_existing_github_releases(repo_slug: str | None, tag_prefix: str, token: str | None) -> set[str]:
    """Consulta la API de GitHub para obtener los tags de los releases existentes en el repo de stubs."""
    if not repo_slug:
        logger.warning("⚠ No se especificó el repositorio de stubs. No se verificará en GitHub.")
        return set()

    tags = set()
    url = f"https://api.github.com/repos/{repo_slug}/releases?per_page=100"
    logger.info("🔍 Consultando releases ya publicados en GitHub para %s...", repo_slug)
    try:
        page = 1
        while True:
            page_url = f"{url}&page={page}"
            data = fetch_json(page_url, token)
            if not data:
                break
            for release in data:
                # Ignorar borradores vacíos para que sean regenerados y publicados limpiamente
                if release.get("draft", False) and not release.get("assets", []):
                    continue
                tag = release.get("tag_name", "")
                if tag:
                    if tag_prefix and tag.startswith(tag_prefix):
                        version = tag[len(tag_prefix):]
                        tags.add(version)
                    elif not tag_prefix and not "-" in tag.split(".")[0]:
                        # Release estándar sin prefijo
                        tags.add(tag)
                    else:
                        tags.add(tag)
            if len(data) < 100:
                break
            page += 1
        logger.info("   → %d versiones encontradas en GitHub", len(tags))
    except Exception as e:
        logger.warning("⚠ No se pudo obtener releases existentes de GitHub: %s", e)
    return tags


def get_existing_local_zips(output_dir: Path, software: str) -> set[str]:
    """Lista las versiones ya generadas localmente buscando stubs-*.zip."""
    existing = set()
    prefix = "stubs-" if software == "pocketmine" else f"stubs-{software}-"
    if output_dir.exists():
        for path in output_dir.glob(f"{prefix}*.zip"):
            version = path.name[len(prefix):-len(".zip")]
            if version:
                existing.add(version)
    if existing:
        logger.info("🔍 Detectadas %d versiones locales en %s para %s", len(existing), output_dir, software)
    return existing


# ─── Lógica de Filtrado y Ordenamiento ────────────────────────────────────────

def extract_minor(version: str) -> str | None:
    """Extrae la rama minor (X.Y) de una versión semántica X.Y.Z[-suffix]."""
    try:
        base = version.split("-")[0]
        parts = base.split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
    except Exception:
        pass
    return None


def semver_key(version_str: str) -> tuple[int, ...]:
    """Genera una clave para ordenar versiones de menor a mayor."""
    try:
        base = version_str.split("-")[0]
        parts = []
        for p in base.split("."):
            clean = "".join(c for c in p if c.isdigit())
            if clean:
                parts.append(int(clean))
        return tuple(parts)
    except Exception:
        return (0,)


def filter_candidates(
    raw_releases: list[dict[str, Any]],
    include_prereleases: bool,
) -> list[dict[str, Any]]:
    """
    Filtra drafts, pre-releases si no se solicitan, y conserva solo el
    último patch de cada minor version X.Y.
    """
    candidates = []
    discarded_draft = 0
    discarded_pre = 0

    for r in raw_releases:
        if r.get("draft", False):
            discarded_draft += 1
            continue
        if not include_prereleases and r.get("prerelease", False):
            discarded_pre += 1
            continue
        candidates.append(r)

    logger.info(
        "🗑  Descartados: %d drafts, %d pre-releases → quedan %d",
        discarded_draft,
        discarded_pre,
        len(candidates),
    )

    # Conservar solo el patch más reciente para cada rama minor
    seen: dict[str, str] = {}
    result = []

    for r in candidates:
        tag = r.get("tag_name", "")
        clean_tag = tag.lstrip("v")
        minor = extract_minor(clean_tag)

        if minor is None:
            result.append(r)
            continue

        if minor not in seen:
            seen[minor] = tag
            result.append(r)
        else:
            logger.debug(
                "  ↷ Descartado %s (ya cubierto por %s en rama %s)",
                tag,
                seen[minor],
                minor,
            )

    logger.info("🎯 Candidatos tras deduplicar por minor: %d", len(result))
    return result


# ─── Generación de Stubs ──────────────────────────────────────────────────────

def generate_stubs(
    version: str,
    software: str,
    workdir: Path,
    output_dir: Path,
    skip_phpstorm: bool = False,
    clean: bool = True,
    repo: str | None = None,
    forks_file: Path | None = None,
) -> tuple[bool, str | None]:
    """Genera stubs para una versión ejecutando generator/generate.py."""
    cmd = [
        "python3",
        str(GENERATOR_SCRIPT),
        f"--version={version}",
        f"--software={software}",
        f"--workdir={workdir}",
        f"--output={output_dir}",
    ]

    if repo:
        cmd.append(f"--repo={repo}")
    if forks_file:
        cmd.append(f"--forks-file={forks_file}")
    if skip_phpstorm:
        cmd.append("--skip-phpstorm")
    if clean:
        cmd.append("--clean")

    logger.info("▶ Ejecutando: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos
        )

        if result.returncode != 0:
            logger.error("❌ Generación falló para %s", version)
            logger.error("   STDERR: %s", result.stderr[-300:])
            return False, f"Exit code {result.returncode}"

        # El SHA256 es la última línea del stdout
        lines = result.stdout.strip().split("\n")
        sha256 = lines[-1] if lines else None

        if not sha256 or len(sha256.strip()) != 64:
            logger.error("❌ SHA256 inválido para %s: %s", version, sha256)
            return False, f"SHA256 inválido: {sha256}"

        logger.info("✅ Stubs generados para %s", version)
        logger.info("   SHA256: %s", sha256)
        return True, sha256

    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout (>10min) generando %s", version)
        return False, "Timeout"
    except Exception as e:
        logger.error("❌ Error generando %s: %s", version, e)
        return False, str(e)


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera stubs PHP de PocketMine-MP y sus forks en batch de forma unificada"
    )
    parser.add_argument(
        "--software",
        type=str,
        default="pocketmine",
        help="Software o fork a procesar (default: pocketmine, ej: altay)",
    )
    parser.add_argument(
        "--forks-file",
        type=Path,
        default=FORKS_FILE,
        help="Ruta personalizada al archivo forks.json",
    )
    parser.add_argument(
        "--source-repo",
        type=str,
        default=None,
        help="Repositorio fuente de releases (sobrescribe forks.json)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Token de GitHub. Si no se pasa, se lee de $GITHUB_TOKEN",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Repositorio de stubs actual para verificar releases (ej: ImAMadDev/pocketmine-stubs)",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=PROJECT_ROOT / "workdir",
        help="Directorio de trabajo (default: workdir)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=PROJECT_ROOT / "output",
        help="Directorio de salida (default: output)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo número de versiones a generar",
    )
    parser.add_argument(
        "--include-prereleases",
        action="store_true",
        help="Generar stubs también para pre-releases (por defecto se excluyen)",
    )
    parser.add_argument(
        "--skip-phpstorm",
        action="store_true",
        help="Omitir descarga de phpstorm-stubs fork (más rápido)",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No limpiar workdir entre generaciones",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar qué versiones se generarían, sin ejecutar el generador",
    )
    parser.add_argument(
        "--generated-only",
        action="store_true",
        help="Mostrar solo versiones ya generadas localmente o en GitHub y salir",
    )
    parser.add_argument(
        "--print-pending",
        action="store_true",
        help="Imprimir los tags de las versiones pendientes a stdout y salir",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Habilita logging DEBUG",
    )
    return parser.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if not GENERATOR_SCRIPT.exists():
        logger.error("❌ No se encontró el generador: %s", GENERATOR_SCRIPT)
        sys.exit(1)

    fork_cfg = load_fork_config(args.software, args.forks_file)
    source_repo = args.source_repo or fork_cfg["repo"]

    if not source_repo:
        logger.error("❌ No se pudo determinar el repositorio fuente para %s. Usa --source-repo.", args.software)
        sys.exit(1)

    token = _get_token(args.token)
    if token:
        logger.info("🔑 Usando token de GitHub")
    else:
        logger.warning(
            "⚠ Sin token de GitHub. Sujeto a rate limits de la API. Usa --token o $GITHUB_TOKEN"
        )

    repo_slug = get_repo_slug(args.repo)

    # 1. Obtener versiones ya existentes
    existing_github = get_existing_github_releases(repo_slug, fork_cfg["tag_prefix"], token)
    existing_local = get_existing_local_zips(args.output, args.software)
    already_generated = existing_github.union(existing_local)

    # Modo de solo consulta
    if args.generated_only:
        logger.info("📊 Resumen de versiones ya generadas para %s:", fork_cfg["name"])
        logger.info("   Total local:  %d", len(existing_local))
        logger.info("   Total GitHub: %d", len(existing_github))
        logger.info("   Total único:  %d", len(already_generated))
        for v in sorted(already_generated, key=semver_key):
            logger.info("   ✓ %s", v)
        return

    # 2. Descargar todos los releases del software
    logger.info("🚀 Iniciando descarga de releases de %s (%s)...", fork_cfg["name"], source_repo)
    raw_releases = fetch_all_releases(source_repo, token)
    logger.info("📦 Total de releases descargados: %d", len(raw_releases))

    # 3. Filtrar candidatos
    candidates = filter_candidates(raw_releases, args.include_prereleases)

    # 4. Determinar pendientes
    pending_candidates = []
    for r in candidates:
        tag = r["tag_name"].lstrip("v")
        if tag not in already_generated and r["tag_name"] not in already_generated:
            pending_candidates.append(r)

    # 5. Ordenar las pendientes de menor a mayor
    pending_candidates.sort(key=lambda r: semver_key(r["tag_name"].lstrip("v")))

    # Validar y limitar a las versiones que procesaremos
    to_process = []
    for r in pending_candidates:
        if args.limit is not None and len(to_process) >= args.limit:
            break

        tag = r["tag_name"].lstrip("v")
        # Validación de build_info.json solo para pmmp
        if args.software == "pocketmine":
            logger.info("🔍 Validando build_info.json para candidate %s...", tag)
            build_info = fetch_build_info(r["tag_name"], source_repo, token)
            if build_info is None:
                logger.warning("  ✗ No se pudo descargar build_info.json para %s. Saltando.", tag)
                continue
            missing = [f for f in REQUIRED_FIELDS if f not in build_info]
            if missing:
                logger.warning(
                    "  ✗ Faltan campos requeridos en build_info.json para %s: %s. Saltando.",
                    tag,
                    ", ".join(missing),
                )
                continue

        to_process.append(r)

    if args.print_pending:
        for r in to_process:
            print(r["tag_name"].lstrip("v"))
        return

    if not to_process:
        logger.info("✓ No hay versiones nuevas pendientes de generar para %s.", fork_cfg["name"])
        return

    logger.info("📋 Versiones pendientes detectadas (%s, ordenadas de menor a mayor):", fork_cfg["name"])
    for r in to_process:
        prefix = "🔴 pre" if r.get("prerelease") else "🟢 rel"
        logger.info("   %s %s", prefix, r["tag_name"])

    if args.dry_run:
        logger.info("✓ Modo dry-run completado (sin ejecutar generación).")
        return

    # 6. Ejecutar la generación secuencial
    logger.info("")
    logger.info("=" * 60)
    logger.info("INICIANDO GENERACIÓN EN BATCH (%s)", fork_cfg["name"].upper())
    logger.info("=" * 60)

    success_count = 0
    fail_count = 0

    for i, release in enumerate(to_process, 1):
        raw_tag = release["tag_name"]
        version = raw_tag.lstrip("v")
        logger.info("")
        logger.info("[%d/%d] Generando stubs para %s %s...", i, len(to_process), fork_cfg["name"], version)

        success, result = generate_stubs(
            version=version,
            software=args.software,
            workdir=args.workdir,
            output_dir=args.output,
            skip_phpstorm=args.skip_phpstorm,
            clean=not args.no_clean,
            repo=args.source_repo,
            forks_file=args.forks_file,
        )

        if success:
            success_count += 1
        else:
            fail_count += 1
            logger.warning("⚠ Falló la generación de stubs para %s: %s", version, result)

    # Resumen
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMEN DE BATCH (%s)", fork_cfg["name"].upper())
    logger.info("=" * 60)
    logger.info("✅ Exitosas:  %d/%d", success_count, len(to_process))
    logger.info("❌ Fallidas:  %d/%d", fail_count, len(to_process))

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
