default: ci

release tag:
    just release-prepare {{tag}}
    just release-publish {{tag}}

release-prepare tag:
    #!/usr/bin/env bash
    set -euo pipefail

    tag='{{tag}}'
    manifest='custom_components/schneider_ups_nmc3/manifest.json'

    if [[ ! "$tag" =~ ^v[0-9]+[.][0-9]+[.][0-9]+([.-][0-9A-Za-z][0-9A-Za-z.-]*)?$ ]]; then
      echo "release tag must look like v0.1.0 or v0.1.0-rc.1" >&2
      exit 2
    fi

    if [[ -n "$(git status --porcelain)" ]]; then
      echo "working tree must be clean before preparing a release" >&2
      exit 1
    fi

    if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
      echo "local tag already exists: $tag" >&2
      exit 1
    fi

    if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
      echo "remote tag already exists: $tag" >&2
      exit 1
    fi

    python - "$tag" "$manifest" <<'PY'
    import json
    import pathlib
    import sys

    tag = sys.argv[1]
    manifest = pathlib.Path(sys.argv[2])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = tag
    manifest.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    PY

    just ci
    git add "$manifest"
    git commit -m "chore: release $tag"

release-publish tag:
    #!/usr/bin/env bash
    set -euo pipefail

    tag='{{tag}}'
    manifest='custom_components/schneider_ups_nmc3/manifest.json'

    if [[ ! "$tag" =~ ^v[0-9]+[.][0-9]+[.][0-9]+([.-][0-9A-Za-z][0-9A-Za-z.-]*)?$ ]]; then
      echo "release tag must look like v0.1.0 or v0.1.0-rc.1" >&2
      exit 2
    fi

    manifest_version="$(python - "$manifest" <<'PY'
    import json
    import pathlib
    import sys

    manifest = pathlib.Path(sys.argv[1])
    print(json.loads(manifest.read_text(encoding="utf-8"))["version"])
    PY
    )"

    if [[ "$manifest_version" != "$tag" ]]; then
      echo "manifest version is $manifest_version, expected $tag" >&2
      exit 1
    fi

    if [[ -n "$(git status --porcelain)" ]]; then
      echo "working tree must be clean before publishing a release" >&2
      exit 1
    fi

    if git rev-parse -q --verify "refs/tags/$tag" >/dev/null; then
      echo "local tag already exists: $tag" >&2
      exit 1
    fi

    if git ls-remote --exit-code --tags origin "refs/tags/$tag" >/dev/null 2>&1; then
      echo "remote tag already exists: $tag" >&2
      exit 1
    fi

    if gh release view "$tag" >/dev/null 2>&1; then
      echo "GitHub release already exists: $tag" >&2
      exit 1
    fi

    just ci
    git tag -s "$tag" -m "$tag"
    git push origin HEAD
    git push origin "$tag"
    gh release create "$tag" --verify-tag --title "$tag" --generate-notes --latest

lock:
    uv lock

lock-check:
    uv lock --check

format:
    uv run ruff format .

format-check:
    uv run ruff format --check .

lint:
    uv run ruff check .

doclint:
    uv run pydoclint custom_components tests

typecheck:
    uv run pyright

spellcheck:
    uv run codespell --ignore-words-list hass AGENTS.md README.md custom_components tests hacs.json justfile pyproject.toml .github/workflows

json:
    uv run python -m json.tool custom_components/schneider_ups_nmc3/manifest.json > /dev/null
    uv run python -m json.tool custom_components/schneider_ups_nmc3/strings.json > /dev/null
    uv run python -m json.tool custom_components/schneider_ups_nmc3/translations/en.json > /dev/null
    uv run python -m json.tool hacs.json > /dev/null

yaml:
    uv run yamllint .github/workflows

test:
    PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests

ci: lock-check format-check lint doclint typecheck spellcheck json yaml test
