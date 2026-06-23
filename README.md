# finops-billing

Monorepo Python (workspace `uv`) com a biblioteca interna compartilhada (`libs/billing_common`)
e os pipelines de dados (`pipelines/<camada>`) do ambiente moderno de billing.

Para contexto de negócio, prioridades de migração e débitos técnicos do legado a não repetir,
ver `CLAUDE.md` na raiz do repositório.

## Pré-requisitos

- Python 3.12 (ver `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) — `pip install uv` ou `pipx install uv`

## Estrutura

```
libs/billing_common/      # biblioteca interna: adapters, logging, config, dates
pipelines/silver/         # camada Silver do medalhão gcp_labels (primeira de 5)
```

## Como rodar localmente

Instalar todas as dependências do workspace (lib + pipelines) em um único ambiente:

```bash
uv sync --all-packages
```

Rodar toda a suíte de testes:

```bash
uv run pytest
```

Rodar testes de um pacote específico:

```bash
uv run pytest libs/billing_common/tests
uv run pytest pipelines/silver/tests
```

Lint e formatação (Ruff substitui black+flake8+isort):

```bash
uv run ruff check .
uv run ruff format .
```

Type checking (modo permissivo, não bloqueia o CI nesta entrega):

```bash
uv run mypy libs pipelines
```

## Adicionando um novo pipeline

1. Criar `pipelines/<nome>/` com `src/<nome>_pipeline/` (layout `src/`) e `tests/`.
2. No `pyproject.toml` do novo pipeline, declarar `billing-common` como dependência:
   ```toml
   [tool.uv.sources]
   billing-common = { workspace = true }
   ```
3. Nunca duplicar `utils/logger.py`, `utils/env_configs.py`, `utils/date.py` ou
   `adapters/bigquery_adapter.py` — importar de `billing_common`.
4. Criar uma subclasse de `BaseEnvConfigs` só com as variáveis de ambiente que o pipeline
   de fato usa (ver `pipelines/silver/src/silver_pipeline/config/env_configs.py` como
   referência).
5. Rodar `uv sync --all-packages` na raiz para o novo membro do workspace ser resolvido.

## Workspace `uv`

A raiz define `[tool.uv.workspace] members = ["libs/*", "pipelines/*"]`. Todos os
`pyproject.toml` do workspace resolvem para um único `uv.lock` (versionado no git) —
não criar lockfiles individuais por pacote.

## CI

`.gitlab-ci.yml` define dois estágios: `lint` (ruff bloqueante, mypy permissivo) e `test`
(um job de pytest por pacote do workspace). Ver o próprio arquivo para detalhes.
