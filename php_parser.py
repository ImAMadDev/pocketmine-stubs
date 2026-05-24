"""
php_parser.py — PocketIDE / pocketmine-stubs
Regex-based PHP parser para extraer firmas de clases, métodos,
propiedades, constantes y funciones de los archivos fuente de PocketMine-MP.
"""

from __future__ import annotations

import re
from typing import Any


class PHPParser:
    """
    Parser PHP puramente basado en expresiones regulares.
    No requiere dependencias externas ni PHP instalado para el parsing.
    Diseñado para generar stubs (solo firmas, sin implementación).
    """

    # ─── Patrones de compilación ─────────────────────────────────────────────

    _RE_NAMESPACE = re.compile(r"^\s*namespace\s+([\w\\]+)\s*;", re.MULTILINE)
    _RE_USE = re.compile(r"^\s*use\s+([\w\\]+)(?:\s+as\s+(\w+))?\s*;", re.MULTILINE)

    _RE_CLASS = re.compile(
        r"(?P<doc>/\*\*(?:(?!\*/).)*\*/\s*)?"
        r"(?:(?P<abstract>abstract)\s+)?(?:(?P<final>final)\s+)?"
        r"(?P<type>class|interface|trait|enum)\s+(?P<name>\w+)"
        r"(?:\s+extends\s+(?P<extends>[\w\\]+))?"
        r"(?:\s+implements\s+(?P<implements>[\w\\,\s]+))?"
        r"\s*\{",
        re.DOTALL | re.IGNORECASE,
    )

    _RE_METHOD = re.compile(
        r"(?P<doc>/\*\*(?:(?!\*/).)*\*/\s*)?"
        r"(?:(?P<visibility>public|protected|private)\s+)?"
        r"(?:(?P<static>static)\s+)?"
        r"(?:(?P<abstract>abstract)\s+)?"
        r"(?:(?P<final>final)\s+)?"
        r"function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
        r"(?:\s*:\s*(?P<return_type>[\w\\|\?\s]+))?",
        re.DOTALL | re.IGNORECASE,
    )

    _RE_PROPERTY = re.compile(
        r"(?P<doc>/\*\*(?:(?!\*/).)*\*/\s*)?"
        r"(?:(?P<visibility>public|protected|private)\s+)?"
        r"(?:(?P<static>static)\s+)?"
        r"(?:(?P<readonly>readonly)\s+)?"
        r"(?P<type>[\w\\|?]+(?:\s+[\w\\|?]+)*)?"
        r"\s*\$(?P<name>\w+)"
        r"(?:\s*=\s*(?P<default>[^;]+))?;",
        re.IGNORECASE,
    )

    _RE_CLASS_CONST = re.compile(
        r"(?:(?P<visibility>public|protected|private)\s+)?"
        r"const\s+(?P<name>\w+)\s*=\s*(?P<value>[^;]+);",
        re.IGNORECASE,
    )

    _RE_GLOBAL_FUNC = re.compile(
        r"(?P<doc>/\*\*(?:(?!\*/).)*\*/\s*)?"
        r"^function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
        r"(?:\s*:\s*(?P<return_type>[\w\\|\?\s]+))?",
        re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )

    _RE_DEFINE_CONST = re.compile(
        r"""define\s*\(\s*['"](?P<name>[\w\\]+)['"]\s*,\s*(?P<value>[^)]+)\)""",
        re.IGNORECASE,
    )

    _RE_PARAM = re.compile(
        r"(?:(?P<type>[\w\\|\?]+)\s+)?"
        r"(?P<ref>&)?"
        r"(?P<variadic>\.\.\.)?"
        r"\$(?P<name>\w+)"
        r"(?:\s*=\s*(?P<default>[^,]+))?",
        re.IGNORECASE,
    )

    # ─── API pública ──────────────────────────────────────────────────────────

    def parse(self, content: str, file_path: str) -> dict[str, Any]:
        """
        Parsea el contenido de un archivo PHP y retorna un dict con:
        namespace, uses, classes, interfaces, traits, functions, constants
        """
        result: dict[str, Any] = {
            "namespace": None,
            "uses": [],
            "classes": {},
            "interfaces": {},
            "traits": {},
            "functions": {},
            "constants": {},
            "file_path": file_path,
        }

        ns_match = self._RE_NAMESPACE.search(content)
        if ns_match:
            result["namespace"] = ns_match.group(1)

        for use_m in self._RE_USE.finditer(content):
            alias = use_m.group(2) or use_m.group(1).split("\\")[-1]
            result["uses"].append({"full_name": use_m.group(1), "alias": alias})

        self._parse_type_declarations(content, result, file_path)
        self._parse_global_functions(content, result)
        self._parse_global_constants(content, result)

        return result

    # ─── Internos ─────────────────────────────────────────────────────────────

    def _parse_type_declarations(
        self, content: str, result: dict, file_path: str
    ) -> None:
        """Parsea class / interface / trait / enum"""
        for m in self._RE_CLASS.finditer(content):
            name = m.group("name")
            kind = m.group("type").lower()

            implements_raw = m.group("implements") or ""
            implements = [s.strip() for s in implements_raw.split(",") if s.strip()]

            info: dict[str, Any] = {
                "name": name,
                "kind": kind,
                "namespace": result["namespace"],
                "full_name": self._fqn(result["namespace"], name),
                "is_abstract": bool(m.group("abstract")),
                "is_final": bool(m.group("final")),
                "extends": m.group("extends"),
                "implements": implements,
                "methods": {},
                "properties": {},
                "constants": {},
                "doc": self._clean_doc(m.group("doc") or ""),
                "file_path": file_path,
                "source": "",
            }

            try:
                body = self._extract_body(content, m.end())
                self._parse_methods(body, info)
                self._parse_properties(body, info)
                self._parse_class_constants(body, info)
            except Exception:
                pass  # continuar con lo que se pudo parsear

            bucket = (
                "classes"
                if kind in ("class", "enum")
                else ("interfaces" if kind == "interface" else "traits")
            )
            result[bucket][name] = info

    def _parse_methods(self, body: str, info: dict) -> None:
        if not body:
            return
        for m in self._RE_METHOD.finditer(body):
            mname = m.group("name")
            info["methods"][mname] = {
                "name": mname,
                "visibility": m.group("visibility") or "public",
                "is_static": bool(m.group("static")),
                "is_abstract": bool(m.group("abstract")),
                "is_final": bool(m.group("final")),
                "parameters": self._parse_params(m.group("params") or ""),
                "return_type": (m.group("return_type") or "mixed").strip(),
                "doc": self._clean_doc(m.group("doc") or ""),
            }

    def _parse_properties(self, body: str, info: dict) -> None:
        if not body:
            return

        # Remover el contenido de los metodos para evitar capturar variables locales
        # como propiedades de clase
        body_without_methods = self._remove_method_bodies(body)

        for m in self._RE_PROPERTY.finditer(body_without_methods):
            pname = m.group("name")
            info["properties"][pname] = {
                "name": pname,
                "visibility": m.group("visibility") or "public",
                "is_static": bool(m.group("static")),
                "is_readonly": bool(m.group("readonly")),
                "type": (m.group("type") or "mixed").strip(),
                "default_value": (m.group("default") or "").strip() or None,
                "doc": self._clean_doc(m.group("doc") or ""),
            }

    def _parse_class_constants(self, body: str, info: dict) -> None:
        if not body:
            return
        for m in self._RE_CLASS_CONST.finditer(body):
            cname = m.group("name")
            val = m.group("value").strip()
            info["constants"][cname] = {
                "name": cname,
                "value": val,
                "visibility": m.group("visibility") or "public",
                "type": self._infer_type(val),
            }

    def _parse_global_functions(self, content: str, result: dict) -> None:
        for m in self._RE_GLOBAL_FUNC.finditer(content):
            fname = m.group("name")
            if self._inside_class(content, m.start()):
                continue
            result["functions"][fname] = {
                "name": fname,
                "namespace": result["namespace"],
                "full_name": self._fqn(result["namespace"], fname),
                "parameters": self._parse_params(m.group("params") or ""),
                "return_type": (m.group("return_type") or "mixed").strip(),
                "doc": self._clean_doc(m.group("doc") or ""),
                "source": "",
            }

    def _parse_global_constants(self, content: str, result: dict) -> None:
        # define('NAME', value)
        for m in self._RE_DEFINE_CONST.finditer(content):
            cname = m.group("name")
            val = m.group("value").strip()
            result["constants"][cname] = {
                "name": cname,
                "namespace": result["namespace"],
                "full_name": self._fqn(result["namespace"], cname),
                "value": val,
                "type": self._infer_type(val),
                "source": "",
            }

    def _parse_params(self, raw: str) -> list[dict[str, Any]]:
        if not raw.strip():
            return []
        params = []
        for m in self._RE_PARAM.finditer(raw):
            params.append(
                {
                    "name": m.group("name"),
                    "type": (m.group("type") or "mixed").strip(),
                    "is_reference": bool(m.group("ref")),
                    "is_variadic": bool(m.group("variadic")),
                    "default_value": (m.group("default") or "").strip() or None,
                    "is_optional": m.group("default") is not None,
                }
            )
        return params

    # ─── Utilidades ───────────────────────────────────────────────────────────

    @staticmethod
    def _remove_method_bodies(body: str) -> str:
        """
        Remueve el contenido de todos los metodos del body.
        Reemplaza lo que hay entre las llaves de cada metodo con espacios en blanco
        para mantener las posiciones, pero sin las variables locales.

        Esto permite que _RE_PROPERTY solo capture propiedades a nivel de clase.
        """
        result = list(body)

        # Encontrar todos los metodos: function name(...) : returnType { ... }
        # Más específico para evitar capturar parámetros con visibility
        method_pattern = re.compile(
            r"(?:(?:public|protected|private)\s+)?"
            r"(?:static\s+)?"
            r"(?:abstract\s+)?"
            r"(?:final\s+)?"
            r"function\s+\w+\s*\([^)]*\)"
            r"(?:\s*:\s*[^{]*)?"
            r"\s*\{",
            re.IGNORECASE,
        )

        for match in method_pattern.finditer(body):
            method_start = match.end()
            # Encontrar la llave de cierre correspondiente
            depth = 1
            i = method_start
            while i < len(body) and depth > 0:
                if body[i] == "{":
                    depth += 1
                elif body[i] == "}":
                    depth -= 1
                i += 1

            if depth == 0:
                # Reemplazar el contenido del metodo con espacios en blanco
                # para mantener posiciones
                method_body_end = i - 1  # posicion de la llave de cierre

                # Rellenar el contenido con espacios
                for j in range(method_start, method_body_end):
                    result[j] = " "

        return "".join(result)

    @staticmethod
    def _extract_body(content: str, start: int) -> str:
        """
        Extrae el cuerpo entre llaves a partir de `start`.

        Nota: Cuando se llama desde _parse_type_declarations, `start` apunta
        justo después del '{' que cierra la declaración de clase.
        Por eso primero retrocedemos para encontrar ese '{'.
        """
        # Retroceder desde start para encontrar el '{' que pertenece a la declaración
        opening_brace_pos = start - 1

        # Asegurarse de que realmente es '{'
        if opening_brace_pos >= 0 and content[opening_brace_pos] != "{":
            # Si no, buscar el próximo '{' (caso de declaraciones con espacios)
            opening_brace_pos = content.find("{", start)

        if opening_brace_pos < 0:
            return ""

        depth = 1  # Ya contamos el '{' inicial
        body_start = opening_brace_pos + 1

        for i in range(opening_brace_pos + 1, len(content)):
            ch = content[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return content[body_start:i]

        return content[body_start:]

    @staticmethod
    def _inside_class(content: str, pos: int) -> bool:
        before = content[:pos]
        classes = len(re.findall(r"\b(?:class|interface|trait)\s+\w+", before, re.I))
        return classes > 0 and before.count("{") > before.count("}")

    @staticmethod
    def _clean_doc(doc: str) -> str:
        if not doc:
            return ""
        lines = [
            re.sub(r"^/?\*+/?", "", ln).strip()
            for ln in doc.splitlines()
            if ln.strip() not in ("/**", "*/", "*")
        ]
        return "\n".join(ln for ln in lines if ln)

    @staticmethod
    def _fqn(namespace: str | None, name: str) -> str:
        return f"{namespace}\\{name}" if namespace else name

    @staticmethod
    def _infer_type(value: str) -> str:
        if value.startswith(("'", '"')):
            return "string"
        if value.lower() in ("true", "false"):
            return "bool"
        if value.lower() == "null":
            return "null"
        try:
            int(value)
            return "int"
        except ValueError:
            pass
        try:
            float(value)
            return "float"
        except ValueError:
            pass
        return "mixed"
