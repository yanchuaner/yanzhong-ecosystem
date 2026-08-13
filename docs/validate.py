#!/usr/bin/env python3
"""Validate the Yanzhong Ecosystem governance repository and workspace."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "repos.yaml"
REGISTRY_SCHEMA_PATH = ROOT / "docs/schemas/repository-registry.v1.schema.json"
SKIP_PARTS = {".git", ".next", ".venv", "build", "coverage", "dist", "node_modules"}
DOCUMENT_SUFFIXES = {".md", ".txt"}
BRAND_SUFFIXES = {".css", ".html", ".js", ".json", ".jsx", ".ts", ".tsx"}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)|!\[[^\]]*\]\(([^)]+)\)")
FORBIDDEN_BRAND_RE = re.compile(r"(?i)\byanchuan\b|yanchuan_alumni|燕川\s*生态")
FORBIDDEN_PRODUCT_BRAND_RE = re.compile(
    r"(?i)\byanchuaner\s+(ecosystem|api|ai|lab)\b"
)
FORBIDDEN_WRITING = (
    "作为一个 AI",
    "作为AI",
    "当然可以",
    "接下来我",
    "下面我",
    "让我来",
    "希望这能帮到你",
)

ROOT_DOCUMENTS = (
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "NOTICE",
    "TRADEMARKS.md",
)

ROOT_REQUIRED_FILES = ROOT_DOCUMENTS + (
    ".editorconfig",
    ".gitattributes",
    ".gitignore",
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/pull_request_template.md",
    ".github/workflows/governance.yml",
    "Makefile",
    "repos.yaml",
    "requirements.in",
    "requirements.txt",
    "scripts/workspace.py",
    "docs/README.md",
    "docs/architecture.md",
    "docs/contracts.md",
    "docs/燕中生态项目关系.txt",
)

PROJECT_REQUIRED_ROOT_FILES = (
    "AGENTS.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "NOTICE",
    "README.md",
    "SECURITY.md",
)

BRAND_POLICY_REQUIREMENTS = {
    "AGENTS.md": (
        "“燕中”与 `yanchuaner` 均为生态 IP 和核心关键词",
        "生态正式名称只使用“燕中生态 / Yanzhong Ecosystem”",
    ),
    "docs/brand.md": (
        "生态正式名称只使用“燕中生态”",
        "英文名称只使用 `Yanzhong Ecosystem`",
    ),
}

MANIFEST_LIST_FIELDS = (
    "data_authorities",
    "integration_dependencies",
    "required_documents",
    "documentation_roots",
)

MANIFEST_PATH_FIELDS = (
    "required_documents",
    "documentation_roots",
    "additional_governance_files",
    "brand_surface_roots",
    "brand_surface_files",
    "license_metadata",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("auto", "standalone", "workspace"),
        default=os.environ.get("YANZHONG_VALIDATION_MODE", "auto"),
        help="standalone validates this repository; workspace also audits registered checkouts",
    )
    return parser.parse_args()


def safe_relative_path(raw: str) -> bool:
    path = Path(raw)
    return bool(raw) and not path.is_absolute() and ".." not in path.parts


def load_registry(errors: list[str]) -> list[dict[str, object]]:
    try:
        data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        errors.append(f"repos.yaml: invalid registry: {exc}")
        return []

    try:
        schema = json.loads(REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.absolute_path) or "root"
            errors.append(f"repos.yaml:{location}: {error.message}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"repository registry schema unavailable: {exc}")
        return []

    if not isinstance(data, dict) or not isinstance(data.get("repositories"), list):
        return []
    raw_repositories = [entry for entry in data["repositories"] if isinstance(entry, dict)]
    ecosystem = data.get("ecosystem", {})
    if not isinstance(ecosystem, dict) or ecosystem.get("keywords") != ["燕中", "yanchuaner"]:
        errors.append("repos.yaml: ecosystem.keywords must be exactly [燕中, yanchuaner]")

    repositories: list[dict[str, object]] = []
    ids: set[str] = set()
    directories: set[str] = set()
    repository_urls: set[str] = set()
    authority_owners: dict[str, str] = {}
    dependencies: dict[str, list[str]] = {}

    for entry in raw_repositories:
        repository_id = entry.get("id")
        directory = entry.get("directory")
        repository_url = entry.get("repository")
        if not all(isinstance(value, str) for value in (repository_id, directory, repository_url)):
            continue
        assert isinstance(repository_id, str)
        assert isinstance(directory, str)
        assert isinstance(repository_url, str)
        if not safe_relative_path(directory) or Path(directory).parent != Path("."):
            errors.append(f"repos.yaml: {repository_id}: unsafe directory {directory!r}")
            continue
        repositories.append(entry)
        for value, seen, label in (
            (repository_id, ids, "id"),
            (directory, directories, "directory"),
            (repository_url, repository_urls, "repository URL"),
        ):
            if value in seen:
                errors.append(f"repos.yaml: duplicate repository {label}: {value}")
            seen.add(value)
        if directory != repository_id:
            errors.append(f"repos.yaml: {repository_id}: directory must match id")
        if entry.get("autonomous_license") != "AGPL-3.0-only":
            errors.append(f"repos.yaml: {repository_id}: autonomous license must be AGPL-3.0-only")

        for field in MANIFEST_LIST_FIELDS:
            if not isinstance(entry.get(field), list):
                errors.append(f"repos.yaml: {repository_id}: {field} must be a list")
        for field in MANIFEST_PATH_FIELDS:
            values = entry.get(field, [])
            if not isinstance(values, list):
                errors.append(f"repos.yaml: {repository_id}: {field} must be a list")
                continue
            for value in values:
                if not isinstance(value, str) or not safe_relative_path(value):
                    errors.append(f"repos.yaml: {repository_id}: unsafe {field} path: {value!r}")

        for authority in entry.get("data_authorities", []):
            if not isinstance(authority, str):
                continue
            if authority in authority_owners:
                errors.append(
                    f"repos.yaml: data authority {authority} is owned by both "
                    f"{authority_owners[authority]} and {repository_id}"
                )
            authority_owners[authority] = repository_id
        dependencies[repository_id] = [
            value
            for value in entry.get("integration_dependencies", [])
            if isinstance(value, str)
        ]

    for repository_id, values in dependencies.items():
        related = next(
            (entry.get("related_repositories", []) for entry in repositories if entry.get("id") == repository_id),
            [],
        )
        for dependency in [*values, *[item for item in related if isinstance(item, str)]]:
            if dependency not in ids:
                errors.append(f"repos.yaml: {repository_id}: unknown repository reference {dependency}")
            if dependency == repository_id:
                errors.append(f"repos.yaml: {repository_id}: repository cannot reference itself")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(repository_id: str, trail: list[str]) -> None:
        if repository_id in visiting:
            cycle = " -> ".join((*trail, repository_id))
            errors.append(f"repos.yaml: cyclic integration dependency: {cycle}")
            return
        if repository_id in visited:
            return
        visiting.add(repository_id)
        for dependency in dependencies.get(repository_id, []):
            if dependency in dependencies:
                visit(dependency, [*trail, repository_id])
        visiting.remove(repository_id)
        visited.add(repository_id)

    for repository_id in dependencies:
        visit(repository_id, [])
    return repositories


def project_path(entry: dict[str, object]) -> Path:
    return ROOT / str(entry["directory"])


def resolve_mode(
    requested: str, repositories: list[dict[str, object]], errors: list[str]
) -> str:
    if requested != "auto":
        return requested
    present = {
        str(entry["directory"]): project_path(entry).is_dir()
        for entry in repositories
    }
    if not present or not any(present.values()):
        return "standalone"
    if all(present.values()):
        return "workspace"
    existing = ", ".join(name for name, exists in present.items() if exists)
    missing = ", ".join(name for name, exists in present.items() if not exists)
    errors.append(
        "auto mode found a partial workspace; use --mode standalone intentionally or clone all "
        f"repositories (present: {existing}; missing: {missing})"
    )
    return "workspace"


def root_documents() -> list[Path]:
    paths = [ROOT / name for name in ROOT_DOCUMENTS]
    paths.extend(
        path
        for path in (ROOT / "docs").rglob("*")
        if path.is_file()
        and path.suffix.lower() in DOCUMENT_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
    )
    return paths


def workspace_documents(repositories: list[dict[str, object]]) -> list[Path]:
    paths: list[Path] = []
    for entry in repositories:
        root = project_path(entry)
        paths.extend(root / name for name in PROJECT_REQUIRED_ROOT_FILES if name != "LICENSE")
        paths.extend(root / str(name) for name in entry.get("additional_governance_files", []))
        for name in entry.get("documentation_roots", []):
            documentation_root = root / str(name)
            if not documentation_root.exists():
                continue
            paths.extend(
                path
                for path in documentation_root.rglob("*")
                if path.is_file()
                and path.suffix.lower() in DOCUMENT_SUFFIXES
                and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
            )
    return paths


def governed_documents(mode: str, repositories: list[dict[str, object]]) -> list[Path]:
    paths = root_documents()
    if mode == "workspace":
        paths.extend(workspace_documents(repositories))
    return sorted({path for path in paths if path.exists()})


def link_target(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        value = value[1 : value.index(">")]
    elif ' "' in value:
        value = value.split(' "', 1)[0]
    return unquote(value.split("#", 1)[0].split("?", 1)[0]).strip()


def belongs_to_project(path: Path, repositories: list[dict[str, object]]) -> bool:
    for entry in repositories:
        try:
            path.relative_to(project_path(entry).resolve())
            return True
        except ValueError:
            continue
    return False


def validate_links(
    paths: list[Path], mode: str, repositories: list[dict[str, object]], errors: list[str]
) -> tuple[int, int]:
    checked = 0
    deferred = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = next(group for group in match.groups() if group is not None)
            target = link_target(raw)
            if not target or target.startswith(("data:", "http://", "https://", "mailto:", "tel:")):
                continue
            checked += 1
            if target.startswith("/"):
                continue
            resolved = (path.parent / target).resolve()
            line = text.count("\n", 0, match.start()) + 1
            try:
                resolved.relative_to(ROOT)
            except ValueError:
                errors.append(f"{path.relative_to(ROOT)}:{line}: link leaves workspace: {raw}")
                continue
            if mode == "standalone" and belongs_to_project(resolved, repositories):
                deferred += 1
                continue
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}:{line}: missing link target: {raw}")
    return checked, deferred


def brand_surfaces(mode: str, repositories: list[dict[str, object]]) -> list[Path]:
    if mode != "workspace":
        return []
    paths: list[Path] = []
    for entry in repositories:
        root = project_path(entry)
        paths.extend(root / str(name) for name in entry.get("brand_surface_files", []))
        for name in entry.get("brand_surface_roots", []):
            surface_root = root / str(name)
            if not surface_root.exists():
                continue
            paths.extend(
                path
                for path in surface_root.rglob("*")
                if path.is_file()
                and path.suffix.lower() in BRAND_SUFFIXES
                and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
            )
    return sorted({path for path in paths if path.exists()})


def validate_language(
    documents: list[Path], brand_paths: list[Path], errors: list[str]
) -> None:
    for path in brand_paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_BRAND_RE.search(line):
                errors.append(f"{relative}:{line_number}: forbidden public brand spelling")
            if FORBIDDEN_PRODUCT_BRAND_RE.search(line):
                errors.append(f"{relative}:{line_number}: technical identifier used as product name")

    for path in documents:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN_BRAND_RE.search(line):
                errors.append(f"{relative}:{line_number}: forbidden public brand spelling")
            if FORBIDDEN_PRODUCT_BRAND_RE.search(line):
                errors.append(f"{relative}:{line_number}: technical identifier used as product name")
            for phrase in FORBIDDEN_WRITING:
                if phrase in line:
                    errors.append(f"{relative}:{line_number}: conversational template phrase: {phrase}")


def validate_governance(
    mode: str, repositories: list[dict[str, object]], errors: list[str]
) -> None:
    for name in ROOT_REQUIRED_FILES:
        if not (ROOT / name).is_file():
            errors.append(f"missing governance file: {name}")
    if (ROOT / ".gitmodules").exists():
        errors.append(".gitmodules is not allowed; ecosystem repositories remain independent")
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").exists() else ""
    for entry in repositories:
        directory = str(entry.get("directory", ""))
        if f"/{directory}/" not in ignore:
            errors.append(f".gitignore: missing independent repository boundary /{directory}/")
    if mode != "workspace":
        return
    for entry in repositories:
        repository_id = str(entry.get("id", "unknown"))
        root = project_path(entry)
        for name in PROJECT_REQUIRED_ROOT_FILES:
            if not (root / name).is_file():
                errors.append(f"{repository_id}: missing {name}")
        for name in entry.get("additional_governance_files", []):
            if not (root / str(name)).is_file():
                errors.append(f"{repository_id}: missing governance override {name}")
        for name in entry.get("required_documents", []):
            if not (root / str(name)).is_file():
                errors.append(f"{repository_id}: missing architecture entry {name}")


def validate_brand_policy(errors: list[str]) -> None:
    for name, requirements in BRAND_POLICY_REQUIREMENTS.items():
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for requirement in requirements:
            if requirement not in text:
                errors.append(f"{name}: missing brand policy invariant: {requirement}")


def validate_license_file(path: Path, expected: str, errors: list[str]) -> None:
    relative = path.relative_to(ROOT)
    if path.suffix == ".json" or path.name == "package-lock.json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "package-lock.json":
            value = data.get("packages", {}).get("", {}).get("license")
        else:
            value = data.get("license")
    elif path.suffix == ".toml":
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        value = data.get("project", {}).get("license")
    else:
        errors.append(f"{relative}: unsupported license metadata format")
        return
    if value != expected:
        errors.append(f"{relative}: expected {expected}, found {value!r}")


def validate_licenses(
    mode: str, repositories: list[dict[str, object]], errors: list[str]
) -> None:
    if mode != "workspace":
        return
    for entry in repositories:
        root = project_path(entry)
        expected = str(entry.get("autonomous_license", "AGPL-3.0-only"))
        for name in entry.get("license_metadata", []):
            path = root / str(name)
            if not path.is_file():
                errors.append(f"{path.relative_to(ROOT)}: missing license metadata file")
                continue
            try:
                validate_license_file(path, expected, errors)
            except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
                errors.append(f"{path.relative_to(ROOT)}: invalid metadata: {exc}")


def validate_release_scripts(
    mode: str, repositories: list[dict[str, object]], errors: list[str]
) -> None:
    if mode != "workspace":
        return
    for entry in repositories:
        manifest = entry.get("release_manifest")
        if not isinstance(manifest, str):
            continue
        path = project_path(entry) / manifest
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid release manifest: {exc}")
            continue
        scripts = data.get("scripts", {})
        if not scripts.get("audit:prod"):
            errors.append(f"{path.relative_to(ROOT)}: missing audit:prod script")
        release = scripts.get("release:check", "")
        if "audit:prod" not in release:
            errors.append(f"{path.relative_to(ROOT)}: release:check does not invoke audit:prod")


def canonical_repository_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith("git@github.com:"):
        value = f"https://github.com/{value.removeprefix('git@github.com:')}"
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com":
        value = f"github.com{parsed.path}"
    return value.removesuffix("/").removesuffix(".git").lower()


def validate_checkouts(
    mode: str, repositories: list[dict[str, object]], errors: list[str]
) -> None:
    if mode != "workspace":
        return
    for entry in repositories:
        repository_id = str(entry.get("id", "unknown"))
        root = project_path(entry)
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode or Path(result.stdout.strip()).resolve() != root.resolve():
            errors.append(f"{repository_id}: not an independent Git checkout")
            continue
        remote = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            check=False,
            capture_output=True,
            text=True,
        )
        expected = entry.get("repository")
        if remote.returncode or not isinstance(expected, str):
            errors.append(f"{repository_id}: origin remote is missing")
        elif canonical_repository_url(remote.stdout) != canonical_repository_url(expected):
            errors.append(f"{repository_id}: origin remote does not match repos.yaml")


def validate_dependency_lock(errors: list[str]) -> None:
    requirements_in = ROOT / "requirements.in"
    requirements = ROOT / "requirements.txt"
    if not requirements_in.is_file() or not requirements.is_file():
        return
    for line_number, line in enumerate(requirements_in.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "==" not in stripped:
            errors.append(f"requirements.in:{line_number}: direct dependency must be pinned")
    locked = requirements.read_text(encoding="utf-8")
    if "--hash=sha256:" not in locked:
        errors.append("requirements.txt: dependency hashes are required")


def validate_workflows(errors: list[str]) -> None:
    workflow_root = ROOT / ".github/workflows"
    if not workflow_root.exists():
        return
    action_re = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)@([^\s#]+)", re.MULTILINE)
    for path in sorted((*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8")
        for action, reference in action_re.findall(text):
            if action.startswith("./"):
                continue
            if not re.fullmatch(r"[0-9a-f]{40}", reference):
                errors.append(f"{path.relative_to(ROOT)}: action {action} must use a commit SHA")
        if not re.search(r"(?m)^permissions:\s*\n\s+contents:\s+read\s*$", text):
            errors.append(f"{path.relative_to(ROOT)}: workflow must declare contents: read")


def run_schema_validation(errors: list[str]) -> str:
    schema = subprocess.run(
        [sys.executable, str(ROOT / "docs/schemas/validate.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if schema.returncode:
        errors.append(f"schema validation failed:\n{schema.stdout}{schema.stderr}")
    return schema.stdout.strip()


def main() -> int:
    args = parse_arguments()
    errors: list[str] = []
    repositories = load_registry(errors)
    mode = resolve_mode(args.mode, repositories, errors)
    documents = governed_documents(mode, repositories)
    surfaces = brand_surfaces(mode, repositories)
    links, deferred_links = validate_links(documents, mode, repositories, errors)
    validate_language(documents, surfaces, errors)
    validate_governance(mode, repositories, errors)
    validate_brand_policy(errors)
    validate_licenses(mode, repositories, errors)
    validate_release_scripts(mode, repositories, errors)
    validate_checkouts(mode, repositories, errors)
    validate_dependency_lock(errors)
    validate_workflows(errors)
    schema_output = run_schema_validation(errors)

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"Validation mode: {mode}")
    print(f"Validated repository registry with {len(repositories)} projects")
    print(f"Validated {len(documents)} governed documents and {links} relative links")
    if deferred_links:
        print(f"Deferred {deferred_links} cross-repository links to workspace validation")
    if mode == "workspace":
        print(f"Validated {len(surfaces)} public brand surface files")
    print(schema_output)
    print("Governance, brand, writing style, license, and release-script checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
