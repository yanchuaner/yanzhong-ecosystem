#!/usr/bin/env python3
"""Inspect or bootstrap the repositories registered in repos.yaml."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "repos.yaml"


def load_repositories() -> list[dict[str, object]]:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    repositories = data.get("repositories") if isinstance(data, dict) else None
    if not isinstance(repositories, list):
        raise ValueError("repos.yaml: repositories must be a list")
    return repositories


def repository_path(entry: dict[str, object]) -> Path:
    directory = entry.get("directory")
    if not isinstance(directory, str) or not directory:
        raise ValueError("repos.yaml: every repository needs a directory")
    path = (ROOT / directory).resolve()
    if path.parent != ROOT.resolve():
        raise ValueError(f"unsafe repository directory: {directory}")
    return path


def run_git(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def canonical_repository_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith("git@github.com:"):
        value = f"https://github.com/{value.removeprefix('git@github.com:')}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com":
        return value.removesuffix("/").removesuffix(".git").lower()
    return f"github.com{parsed.path}".removesuffix("/").removesuffix(".git").lower()


def validate_checkout(entry: dict[str, object]) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    path = repository_path(entry)
    repository = entry.get("repository")
    name = str(entry.get("id", path.name))
    if not path.exists():
        return None, [f"{name}: missing checkout at {path}"]
    if not (path / ".git").exists():
        return None, [f"{name}: directory is not an independent Git checkout"]
    if not isinstance(repository, str):
        return None, [f"{name}: manifest repository URL is missing"]
    remote = run_git(path, "remote", "get-url", "origin")
    if remote.returncode:
        errors.append(f"{name}: origin remote is missing")
    elif canonical_repository_url(remote.stdout) != canonical_repository_url(repository):
        errors.append(
            f"{name}: origin mismatch ({remote.stdout.strip()} != {repository})"
        )
    return path, errors


def command_status(repositories: list[dict[str, object]]) -> int:
    errors: list[str] = []
    for entry in repositories:
        name = str(entry.get("id", "unknown"))
        path, entry_errors = validate_checkout(entry)
        errors.extend(entry_errors)
        if path is None:
            print(f"{name}: MISSING")
            continue
        branch = run_git(path, "branch", "--show-current").stdout.strip() or "detached"
        changes = run_git(path, "status", "--short").stdout.splitlines()
        state = "clean" if not changes else f"dirty ({len(changes)} paths)"
        print(f"{name}: {branch}, {state}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


def command_bootstrap(repositories: list[dict[str, object]]) -> int:
    for entry in repositories:
        name = str(entry.get("id", "unknown"))
        path = repository_path(entry)
        repository = entry.get("repository")
        if path.exists():
            print(f"{name}: kept existing checkout")
            continue
        if not isinstance(repository, str):
            print(f"{name}: repository URL is missing", file=sys.stderr)
            return 1
        result = subprocess.run(
            ["git", "clone", "--origin", "origin", repository, str(path)],
            cwd=ROOT,
            check=False,
        )
        if result.returncode:
            return result.returncode
    return command_status(repositories)


def command_diff_check(repositories: list[dict[str, object]]) -> int:
    errors: list[str] = []
    roots = [("yanzhong-ecosystem", ROOT)]
    for entry in repositories:
        path, entry_errors = validate_checkout(entry)
        errors.extend(entry_errors)
        if path is not None:
            roots.append((str(entry.get("id", path.name)), path))
    for name, path in roots:
        result = subprocess.run(["git", "-C", str(path), "diff", "--check"], check=False)
        if result.returncode:
            errors.append(f"{name}: git diff --check failed")
        result = subprocess.run(
            ["git", "-C", str(path), "diff", "--cached", "--check"], check=False
        )
        if result.returncode:
            errors.append(f"{name}: git diff --cached --check failed")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Whitespace checks passed for {len(roots)} repositories")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "bootstrap", "diff-check"))
    args = parser.parse_args()
    try:
        repositories = load_repositories()
        if args.command == "status":
            return command_status(repositories)
        if args.command == "bootstrap":
            return command_bootstrap(repositories)
        return command_diff_check(repositories)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
