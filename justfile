default: ci

release version:
    just release-prepare {{version}}
    SKIP_RELEASE_CI=1 just release-publish {{version}}

release-prepare version:
    #!/usr/bin/env bash
    set -euo pipefail

    requested_version='{{version}}'
    manifest_version="${requested_version#v}"
    tag="v$manifest_version"
    manifest='custom_components/schneider_ups_nmc3/manifest.json'

    if [[ ! "$manifest_version" =~ ^[0-9]+[.][0-9]+[.][0-9]+([.-][0-9A-Za-z][0-9A-Za-z.-]*)?$ ]]; then
      echo "release version must look like 0.1.0, v0.1.0, 0.1.0-rc.1, or v0.1.0-rc.1" >&2
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

    uv run python - "$manifest_version" "$manifest" <<'PY'
    import json
    import pathlib
    import sys

    manifest_version = sys.argv[1]
    manifest = pathlib.Path(sys.argv[2])
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = manifest_version
    manifest.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    PY

    just ci
    git add "$manifest"
    git commit -m "chore: release $tag"

release-publish version:
    #!/usr/bin/env bash
    set -euo pipefail

    requested_version='{{version}}'
    manifest_version="${requested_version#v}"
    tag="v$manifest_version"
    manifest='custom_components/schneider_ups_nmc3/manifest.json'

    if [[ ! "$manifest_version" =~ ^[0-9]+[.][0-9]+[.][0-9]+([.-][0-9A-Za-z][0-9A-Za-z.-]*)?$ ]]; then
      echo "release version must look like 0.1.0, v0.1.0, 0.1.0-rc.1, or v0.1.0-rc.1" >&2
      exit 2
    fi

    current_manifest_version="$(uv run python - "$manifest" <<'PY'
    import json
    import pathlib
    import sys

    manifest = pathlib.Path(sys.argv[1])
    print(json.loads(manifest.read_text(encoding="utf-8"))["version"])
    PY
    )"

    if [[ "$current_manifest_version" != "$manifest_version" ]]; then
      echo "manifest version is $current_manifest_version, expected $manifest_version" >&2
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

    if [[ "${SKIP_RELEASE_CI:-0}" != "1" ]]; then
      just ci
    fi

    git tag -s "$tag" -m "$tag"
    git push origin HEAD
    git push origin "$tag"
    if [[ "$manifest_version" == *-* ]]; then
      gh release create "$tag" --verify-tag --title "$tag" --generate-notes --prerelease
    else
      gh release create "$tag" --verify-tag --title "$tag" --generate-notes --latest
    fi

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
    PYTHONDONTWRITEBYTECODE=1 uv run pytest -q

ci: lock-check format-check lint doclint typecheck spellcheck json yaml test
