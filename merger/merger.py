"""
merger.py — PocketIDE / pocketmine-stubs
Descarga PocketMine-MP.phar y phpstorm-stubs fork, los parsea y fusiona
en un conjunto de archivos PHP stub listos para Intelephense.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

# Add parent directory to path to import php_parser
sys.path.insert(0, str(Path(__file__).parent.parent))
from php_parser import PHPParser

logger = logging.getLogger(__name__)

# ─── URLs ────────────────────────────────────────────────────────────────────

PM_PHAR_URL = (
    "https://github.com/pmmp/PocketMine-MP/releases/latest/download/PocketMine-MP.phar"
)
PHPSTORM_FORK_URL = "https://github.com/pmmp/phpstorm-stubs/archive/refs/heads/fork.zip"

# ─── Versión PM específica (usada desde CLI con --version) ───────────────────

PM_VERSIONED_PHAR_URL = "https://github.com/pmmp/PocketMine-MP/releases/download/{version}/PocketMine-MP.phar"


class StubMerger:
    """
    Pipeline completo:
      1. Descargar PocketMine-MP.phar
      2. Extraerlo con PHP subprocess
      3. Parsear .php con PHPParser
      4. Descargar y parsear phpstorm-stubs fork (menor prioridad)
      5. Generar archivos .php stub por namespace
      6. Crear autocompletion_index.json
      7. Comprimir en stubs.zip
    """

    def __init__(self, workdir: Path, version: str = "latest"):
        self.workdir = Path(workdir)
        self.version = version
        self.parser = PHPParser()

        # Sub-directorios
        self.pm_dir = self.workdir / "pocketmine_phar"
        self.extract_dir = self.workdir / "phar_extracted"
        self.phpstorm_dir = self.workdir / "phpstorm_stubs_fork"
        self.stubs_dir = self.workdir / "stubs"

        # Datos fusionados
        self.classes: dict[str, Any] = {}
        self.interfaces: dict[str, Any] = {}
        self.traits: dict[str, Any] = {}
        self.functions: dict[str, Any] = {}
        self.constants: dict[str, Any] = {}
        self.namespaces: set[str] = set()

        self.stats = {
            "files_processed": 0,
            "classes_found": 0,
            "interfaces_found": 0,
            "traits_found": 0,
            "functions_found": 0,
            "constants_found": 0,
            "parse_errors": 0,
        }

        self.workdir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 1: Descargar PocketMine-MP.phar
    # ──────────────────────────────────────────────────────────────────────────

    def download_phar(self) -> Path:
        self.pm_dir.mkdir(parents=True, exist_ok=True)
        phar_path = self.pm_dir / "PocketMine-MP.phar"

        if phar_path.exists():
            logger.info("📦 PocketMine-MP.phar ya existe, omitiendo descarga.")
            return phar_path

        url = (
            PM_VERSIONED_PHAR_URL.format(version=self.version)
            if self.version != "latest"
            else PM_PHAR_URL
        )

        logger.info(f"📥 Descargando phar desde {url} ...")
        urllib.request.urlretrieve(url, phar_path, reporthook=self._progress_hook)
        logger.info(f"✅ Phar guardado en {phar_path}")
        return phar_path

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 2: Extraer con PHP
    # ──────────────────────────────────────────────────────────────────────────

    def extract_phar(self, phar_path: Path) -> Path:
        if self.extract_dir.exists():
            shutil.rmtree(self.extract_dir)
        self.extract_dir.mkdir(parents=True, exist_ok=True)

        logger.info("📂 Extrayendo phar con PHP...")
        php_code = f"$p = new Phar('{phar_path}'); $p->extractTo('{self.extract_dir}');"
        result = subprocess.run(
            ["php", "-d", "phar.readonly=0", "-r", php_code],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Error extrayendo phar:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )

        logger.info(f"✅ Phar extraído en {self.extract_dir}")
        return self.extract_dir

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 3: Parsear PocketMine-MP
    # ──────────────────────────────────────────────────────────────────────────

    def parse_pocketmine(self, source_dir: Path) -> None:
        logger.info("🔎 Parseando fuentes de PocketMine-MP...")
        self._parse_dir(source_dir, priority=True, source_label="pocketmine")
        self._log_counts("PocketMine-MP")

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 4: Descargar y parsear phpstorm-stubs fork
    # ──────────────────────────────────────────────────────────────────────────

    def download_phpstorm_fork(self) -> None:
        if self.phpstorm_dir.exists():
            logger.info("📦 phpstorm-stubs fork ya existe.")
            return

        zip_path = self.workdir / "phpstorm_fork.zip"
        logger.info("📥 Descargando phpstorm-stubs fork...")
        urllib.request.urlretrieve(
            PHPSTORM_FORK_URL, zip_path, reporthook=self._progress_hook
        )

        with zipfile.ZipFile(zip_path, "r") as zf:
            top = zf.namelist()[0].split("/")[0]
            zf.extractall(self.workdir)

        (self.workdir / top).rename(self.phpstorm_dir)
        zip_path.unlink()
        logger.info(f"✅ phpstorm-stubs fork en {self.phpstorm_dir}")

    def parse_phpstorm_fork(self) -> None:
        logger.info("🔎 Parseando phpstorm-stubs fork...")
        self._parse_dir(self.phpstorm_dir, priority=False, source_label="phpstorm-fork")
        self._log_counts("phpstorm-stubs fork")

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 5: Generar archivos .php stub
    # ──────────────────────────────────────────────────────────────────────────

    def generate_stubs(self) -> None:
        if self.stubs_dir.exists():
            shutil.rmtree(self.stubs_dir)
        self.stubs_dir.mkdir(parents=True, exist_ok=True)

        logger.info("📝 Generando archivos PHP stub...")
        self._write_namespace_files()
        self._write_phpstorm_meta()
        self._write_autocompletion_index()
        logger.info(f"✅ Stubs escritos en {self.stubs_dir}")

    # ──────────────────────────────────────────────────────────────────────────
    # PASO 6: Comprimir en stubs.zip
    # ──────────────────────────────────────────────────────────────────────────

    def zip_stubs(self, output_path: Path) -> str:
        logger.info(f"📦 Comprimiendo stubs en {output_path}...")
        import hashlib

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(self.stubs_dir.rglob("*")):
                if file.is_file():
                    arcname = file.relative_to(self.stubs_dir)
                    zf.write(file, arcname)

        sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
        logger.info(f"✅ ZIP creado: {output_path} (SHA256: {sha256})")
        return sha256

    # ──────────────────────────────────────────────────────────────────────────
    # Orquestador principal
    # ──────────────────────────────────────────────────────────────────────────

    def run(self, output_zip: Path) -> str:
        t0 = time.time()

        phar = self.download_phar()
        extracted = self.extract_phar(phar)
        self.parse_pocketmine(extracted)

        self.download_phpstorm_fork()
        self.parse_phpstorm_fork()

        self.generate_stubs()
        sha256 = self.zip_stubs(output_zip)

        elapsed = round(time.time() - t0, 1)
        logger.info(f"🏁 Completado en {elapsed}s. Stats: {self.stats}")
        return sha256

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers de parsing
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_dir(self, directory: Path, priority: bool, source_label: str) -> None:
        php_files = list(directory.rglob("*.php"))
        total = len(php_files)

        for i, php_file in enumerate(php_files, 1):
            try:
                content = php_file.read_text(encoding="utf-8", errors="ignore")
                parsed = self.parser.parse(content, str(php_file))
                self._merge(parsed, source_label, priority=priority)
                self.stats["files_processed"] += 1
            except Exception as e:
                self.stats["parse_errors"] += 1
                logger.debug(f"Parse error in {php_file}: {e}")

            if i % 500 == 0:
                logger.info(f"  {i}/{total} archivos ({source_label})...")

    def _merge(self, parsed: dict, source: str, priority: bool) -> None:
        if parsed["namespace"]:
            self.namespaces.add(parsed["namespace"])

        for bucket_name in (
            "classes",
            "interfaces",
            "traits",
            "functions",
            "constants",
        ):
            src_bucket = parsed[bucket_name]
            dst_bucket = getattr(self, bucket_name)

            for name, item in src_bucket.items():
                item["source"] = source
                if priority or name not in dst_bucket:
                    dst_bucket[name] = item
                    # Simplify: just count total
                    self.stats[
                        f"{bucket_name.removesuffix('s') if bucket_name not in ('classes', 'interfaces', 'traits') else bucket_name[:-2] + 's' if bucket_name in ('classes', 'traits') else 'interfaces'}_found"
                    ] = len(dst_bucket)

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers de escritura
    # ──────────────────────────────────────────────────────────────────────────

    def _write_namespace_files(self) -> None:
        """Agrupa por namespace y escribe un archivo .php por namespace."""
        ns_map: dict[str, dict] = {}

        def _add(item: dict, bucket: str) -> None:
            ns = item.get("namespace") or "__global__"
            if ns not in ns_map:
                ns_map[ns] = {
                    "classes": [],
                    "interfaces": [],
                    "traits": [],
                    "functions": [],
                    "constants": [],
                }
            ns_map[ns][bucket].append(item)

        for item in self.classes.values():
            _add(item, "classes")
        for item in self.interfaces.values():
            _add(item, "interfaces")
        for item in self.traits.values():
            _add(item, "traits")
        for item in self.functions.values():
            _add(item, "functions")
        for item in self.constants.values():
            _add(item, "constants")

        for ns, items in ns_map.items():
            if ns == "__global__":
                stub_file = self.stubs_dir / "_global.php"
            else:
                parts = ns.replace("\\", "/")
                path = self.stubs_dir / parts
                path.mkdir(parents=True, exist_ok=True)
                stub_file = path / "stubs.php"

            self._write_stub_file(stub_file, ns if ns != "__global__" else None, items)

    def _write_stub_file(self, path: Path, namespace: str | None, items: dict) -> None:
        lines: list[str] = [
            "<?php",
            f"// PocketMine-MP {self.version} stubs — generated by pocketide/pocketmine-stubs",
            "// This file is for IDE autocompletion only. DO NOT EDIT MANUALLY.",
            "// @noinspection PhpIllegalPsrClassPathInspection",
            "",
        ]

        if namespace:
            lines += [f"namespace {namespace};", ""]

        # Interfaces primero, luego traits, luego clases
        for item in items["interfaces"]:
            lines += self._render_interface(item)
        for item in items["traits"]:
            lines += self._render_trait(item)
        for item in items["classes"]:
            lines += self._render_class(item)

        # Funciones y constantes globales
        for fn in items["functions"]:
            lines += self._render_function(fn)
        for const in items["constants"]:
            value = const.get("value", "null")
            lines.append(
                f"define('{const['name']}', {value}); // {const.get('type', 'mixed')}"
            )

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _render_doc(self, doc: str, indent: str = "") -> list[str]:
        if not doc:
            return []
        inner = [f"{indent} * {line}" for line in doc.splitlines() if line.strip()]
        return [f"{indent}/**"] + inner + [f"{indent} */"]

    def _render_class(self, cls: dict) -> list[str]:
        lines = self._render_doc(cls.get("doc", ""))

        decl = ""
        if cls.get("is_abstract"):
            decl += "abstract "
        if cls.get("is_final"):
            decl += "final "
        decl += f"class {cls['name']}"
        if cls.get("extends"):
            decl += f" extends {cls['extends']}"
        if cls.get("implements"):
            decl += f" implements {', '.join(cls['implements'])}"

        lines += [decl, "{"]

        for cname, cdata in (cls.get("constants") or {}).items():
            vis = cdata.get("visibility", "public")
            value = cdata.get("value", "null")
            lines.append(f"    {vis} const {cname} = {value};")

        for pname, pdata in (cls.get("properties") or {}).items():
            vis = pdata.get("visibility", "public")
            static = "static " if pdata.get("is_static") else ""
            readonly = "readonly " if pdata.get("is_readonly") else ""
            ptype = pdata.get("type", "mixed")
            lines += self._render_doc(pdata.get("doc", ""), indent="    ")
            lines.append(f"    {vis} {static}{readonly}{ptype} ${pname};")

        for mdata in (cls.get("methods") or {}).values():
            lines += self._render_method(mdata)

        lines += ["}", ""]
        return lines

    def _render_interface(self, iface: dict) -> list[str]:
        lines = self._render_doc(iface.get("doc", ""))
        decl = f"interface {iface['name']}"
        if iface.get("extends"):
            decl += f" extends {iface['extends']}"
        lines += [decl, "{"]

        for mdata in (iface.get("methods") or {}).values():
            lines += self._render_method(mdata, is_interface=True)

        lines += ["}", ""]
        return lines

    def _render_trait(self, trait: dict) -> list[str]:
        lines = self._render_doc(trait.get("doc", ""))
        lines += [f"trait {trait['name']}", "{"]

        for mdata in (trait.get("methods") or {}).values():
            lines += self._render_method(mdata)

        lines += ["}", ""]
        return lines

    def _render_method(self, m: dict, is_interface: bool = False) -> list[str]:
        lines = self._render_doc(m.get("doc", ""), indent="    ")

        sig = "    "
        if not is_interface:
            sig += m.get("visibility", "public") + " "
            if m.get("is_static"):
                sig += "static "
            if m.get("is_abstract"):
                sig += "abstract "
            if m.get("is_final"):
                sig += "final "

        sig += f"function {m['name']}("
        sig += self._render_params(m.get("parameters", []))
        sig += ")"

        rt = (m.get("return_type") or "mixed").strip()
        if rt and rt != "mixed":
            sig += f": {rt}"

        if is_interface or m.get("is_abstract"):
            sig += ";"
        else:
            sig += " {}"

        lines.append(sig)
        return lines

    def _render_function(self, fn: dict) -> list[str]:
        lines = self._render_doc(fn.get("doc", ""))
        sig = f"function {fn['name']}("
        sig += self._render_params(fn.get("parameters", []))
        sig += ")"
        rt = (fn.get("return_type") or "mixed").strip()
        if rt and rt != "mixed":
            sig += f": {rt}"
        sig += " {}"
        lines += [sig, ""]
        return lines

    @staticmethod
    def _render_params(params: list[dict]) -> str:
        parts = []
        for p in params:
            s = ""
            t = (p.get("type") or "mixed").strip()
            if t and t != "mixed":
                s += t + " "
            if p.get("is_reference"):
                s += "&"
            if p.get("is_variadic"):
                s += "..."
            s += "$" + p["name"]
            if p.get("default_value") and not p.get("is_variadic"):
                s += f" = {p['default_value']}"
            parts.append(s)
        return ", ".join(parts)

    def _write_phpstorm_meta(self) -> None:
        meta = self.stubs_dir / ".phpstorm.meta.php"
        meta.write_text(
            "<?php\n"
            "// PhpStorm metadata for PocketMine-MP\n"
            "namespace PHPSTORM_META {\n"
            "    expectedReturnValues(\n"
            "        \\pocketmine\\Server::getInstance(),\n"
            "        \\pocketmine\\Server::class\n"
            "    );\n"
            "}\n",
            encoding="utf-8",
        )

    def _write_autocompletion_index(self) -> None:
        index = {
            "version": self.version,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "namespaces": sorted(self.namespaces),
            "classes": {
                name: {
                    "namespace": d.get("namespace"),
                    "extends": d.get("extends"),
                    "implements": d.get("implements", []),
                    "is_abstract": d.get("is_abstract", False),
                    "methods": list(d.get("methods", {}).keys()),
                    "properties": list(d.get("properties", {}).keys()),
                    "constants": list(d.get("constants", {}).keys()),
                }
                for name, d in self.classes.items()
            },
            "interfaces": {
                name: {
                    "namespace": d.get("namespace"),
                    "extends": d.get("extends"),
                    "methods": list(d.get("methods", {}).keys()),
                }
                for name, d in self.interfaces.items()
            },
            "traits": {
                name: {
                    "namespace": d.get("namespace"),
                    "methods": list(d.get("methods", {}).keys()),
                }
                for name, d in self.traits.items()
            },
            "functions": {
                name: {
                    "namespace": d.get("namespace"),
                    "return_type": d.get("return_type", "mixed"),
                    "parameters": [
                        {"name": p["name"], "type": p.get("type", "mixed")}
                        for p in d.get("parameters", [])
                    ],
                }
                for name, d in self.functions.items()
            },
            "constants": {
                name: {
                    "namespace": d.get("namespace"),
                    "type": d.get("type", "mixed"),
                }
                for name, d in self.constants.items()
            },
        }

        (self.stubs_dir / "autocompletion_index.json").write_text(
            json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _write_stats(self, output_zip: Path, sha256: str) -> None:
        stats = {
            "version": self.version,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sha256": sha256,
            "zip_path": str(output_zip),
            "classes": len(self.classes),
            "interfaces": len(self.interfaces),
            "traits": len(self.traits),
            "functions": len(self.functions),
            "constants": len(self.constants),
            "namespaces": len(self.namespaces),
            "files_processed": self.stats["files_processed"],
            "parse_errors": self.stats["parse_errors"],
        }
        stats_file = output_zip.parent / f"stats-{self.version}.json"
        stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")
        logger.info(f"📊 Stats guardadas en {stats_file}")

    # ─── Utils ────────────────────────────────────────────────────────────────

    @staticmethod
    def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            downloaded = block_num * block_size
            pct = min(100, downloaded * 100 // total_size)
            mb = downloaded / (1024 * 1024)
            print(f"\r  {pct}%  {mb:.1f} MB", end="", flush=True)
            if pct == 100:
                print()

    def _log_counts(self, label: str) -> None:
        logger.info(
            f"➡ {label}: "
            f"{len(self.classes)} clases, "
            f"{len(self.interfaces)} interfaces, "
            f"{len(self.traits)} traits, "
            f"{len(self.functions)} funciones, "
            f"{len(self.constants)} constantes"
        )
