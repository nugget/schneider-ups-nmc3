default: ci

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
