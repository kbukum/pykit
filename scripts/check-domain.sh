#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -n "${PYTHON:-}" ]]; then
  python_bin="$PYTHON"
elif command -v python3.13 >/dev/null 2>&1; then
  python_bin="python3.13"
else
  python_bin="python3"
fi

require_python() {
  "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 13) else "Python 3.13+ is required")'
}

list_domains() {
  "$python_bin" -c 'import tomllib
with open("domains.toml", "rb") as f:
    data = tomllib.load(f)
for name in sorted(data.get("domains", {})):
    print(name)'
}

read_modules() {
  local domain="$1"
  "$python_bin" -c 'import sys, tomllib
with open("domains.toml", "rb") as f:
    data = tomllib.load(f)
domains = data.get("domains", {})
name = sys.argv[1]
entry = domains.get(name)
if entry is None:
    print(f"Unknown domain: {name}", file=sys.stderr)
    print("Available domains:", file=sys.stderr)
    for item in sorted(domains):
        print(f"  {item}", file=sys.stderr)
    raise SystemExit(1)
for module in entry["modules"]:
    print(module)' "$domain"
}

resolve_package_path() {
  local module="$1"
  local package_path="packages/pykit-$module"
  if [[ "$module" == "pykit" ]]; then
    package_path="packages/pykit"
  fi

  if [[ ! -d "$package_path" ]]; then
    echo "Unable to resolve package for '$module' (expected $package_path)" >&2
    return 1
  fi

  printf '%s\n' "$package_path"
}

run_module_checks() {
  local module="$1"
  local package_path
  package_path="$(resolve_package_path "$module")"

  echo "==> Checking $module ($package_path)"
  uv run pytest "$package_path/"
  uv run ruff check "$package_path/"
  uv run mypy "$package_path/"
}

run_domain() {
  local domain="$1"
  local modules_output
  local -a modules=()
  local module

  modules_output="$(read_modules "$domain")"
  if [[ -n "$modules_output" ]]; then
    while IFS= read -r module; do
      [[ -n "$module" ]] || continue
      modules+=("$module")
    done <<< "$modules_output"
  fi

  echo "==> Domain: $domain"
  for module in "${modules[@]}"; do
    run_module_checks "$module"
  done
}

main() {
  require_python

  if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <domain|--list|--all>" >&2
    exit 1
  fi

  case "$1" in
    --list)
      list_domains
      ;;
    --all)
      local domains_output
      local -a domains=()
      local domain
      domains_output="$(list_domains)"
      if [[ -n "$domains_output" ]]; then
        while IFS= read -r domain; do
          [[ -n "$domain" ]] || continue
          domains+=("$domain")
        done <<< "$domains_output"
      fi
      for domain in "${domains[@]}"; do
        run_domain "$domain"
      done
      ;;
    *)
      run_domain "$1"
      ;;
  esac
}

main "$@"
