# finops-billing

Monorepo Python (workspace `uv`) com a biblioteca interna compartilhada (`libs/billing_common`)
e os pipelines de dados (`pipelines/<camada>`) do ambiente moderno de billing multicloud da
Globo (GCP, AWS, Azure, OCI, Tsuru, DBaaS), usado para chargeback financeiro e dashboards
Looker Studio.

Este repositório é o **destino da modernização** do ambiente legado `gcp-billing`
(`C:\Users\ricar\gcp-billing` localmente). Para contexto de negócio completo, prioridades de
migração e débitos técnicos do legado a não repetir aqui, ver `CLAUDE.md` na raiz do
repositório — leitura obrigatória antes de tocar em qualquer pipeline.

## Objetivo do projeto

Consolidar o billing multicloud em uma arquitetura medalhão de 5 camadas, substituindo as
Cloud Functions duplicadas do legado por pipelines Python organizados em um workspace `uv`
único, com biblioteca compartilhada (`billing_common`) em vez de `utils/`/`adapters/` copiados
em cada Cloud Function.

## Arquitetura resumida

```
silver  →  gold_pre_foundation  →  gold_foundation  →  gold  →  unificado
```

Cada seta representa uma camada do medalhão `gcp_labels` (legado) já migrada para Python neste
repositório, com paridade comportamental confirmada por leitura do código legado. Detalhe
completo (tabelas reais, dependências externas, achados de paridade) em
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) e [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md).

**Importante — não existe orquestrador único ainda**: cada camada acima tem um `main.py`
próprio e independente (`pipelines/<camada>/src/<camada>_pipeline/main.py`), pensado para ser
disparado por uma Cloud Function/Cloud Run Job dedicada por camada. O orquestrador único do
legado (`gcp_labels/main.py`, que decide quais camadas chamar por "modo"/`layer`) **não foi
replicado** nesta entrega.

## Tecnologias

- **Python 3.12** (ver `.python-version`), gerenciado com [`uv`](https://docs.astral.sh/uv/)
  em workspace único (`[tool.uv.workspace] members = ["libs/*", "pipelines/*"]`).
- **BigQuery** (`google-cloud-bigquery`) — cliente real em `libs/billing_common`
  (`billing_common.adapters.bigquery.BigQueryAdapter`).
- **Secret Manager** (`google-cloud-secret-manager`) — cliente real em `libs/billing_common`
  (`billing_common.secrets.secret_manager.get_secret_json`), disponível como infraestrutura
  reutilizável para qualquer pipeline futuro que precise ler credenciais em runtime — sem
  consumidor real hoje nas 5 camadas do medalhão. Não há cliente de Cloud Storage na lib
  compartilhada.
- **Jinja2** — todas as queries SQL das 5 camadas do medalhão são templates Jinja
  (`jinja2.Environment(undefined=jinja2.StrictUndefined)`), renderizados em runtime com
  parâmetros como `invoice_month`, nomes de tabela totalmente qualificados etc.
- **pytest** — suíte de testes por pacote, sem chamadas reais a BigQuery (tudo mockado via
  `unittest.mock.patch`).
- **Ruff** — lint + format (substitui black/flake8/isort), bloqueante no CI.
- **mypy** — type checking, permissivo no CI (não bloqueia hoje).
- **Terraform** (`google` provider `~> 6.0`) — módulos reutilizáveis em `terraform/modules/`
  (`bigquery_table`, `cloud_run_job`, `cloud_scheduler_http`, `secret_manager_secret`), disponíveis
  para qualquer pipeline futuro, mas **sem nenhum módulo instanciado** em
  `terraform/environments/{dev,prod}/` hoje. **Não existe Terraform de deploy para as 5 camadas do
  medalhão ainda** — ver `docs/DEPLOYMENT.md`.
- **GitLab CI** (`.gitlab-ci.yml`) — lint (Ruff bloqueante, mypy permissivo) + test (um job de
  pytest por pacote do workspace). Hoje só há jobs de teste para `billing_common` e `silver` —
  ver lacuna detalhada em `docs/DEPLOYMENT.md`.

## Estrutura do repositório

```
libs/billing_common/                # lib interna compartilhada: adapters, logging, config, dates
  src/billing_common/
    adapters/bigquery.py            # BigQueryAdapter — único adapter real hoje
    config/base.py                  # BaseEnvConfigs — validação de env vars obrigatórias
    dates/date_util.py              # DateUtil — primeiro/último dia do mês, mês anterior etc.
    logging/json_logger.py          # build_logger — logger JSON em stdout (Cloud Logging)
  tests/

pipelines/silver/                   # camada Silver do medalhão (1ª) — gcp_billing_silver_label
pipelines/gold_pre_foundation/       # camada Gold Pre-Foundation (2ª) — tb_gcp_gold_pre_foundation
pipelines/gold_foundation/           # camada Gold Foundation (3ª) — tb_gcp_billing_foundation_labels[_dashboard]
pipelines/gold/                      # camada Gold (4ª) — tb_gcp_billing_projeto_ar_label
pipelines/unificado/                 # camada Unificado (5ª) — tb_gcp_tsuru_dbaas_unificada_labels
  # cada uma das 5 pastas acima segue o mesmo layout:
  src/<nome>_pipeline/
    main.py                         # entry point mínimo (CLI: uv run python -m <nome>_pipeline.main [invoice_month])
    config/env_configs.py           # subclasse de BaseEnvConfigs específica da camada
    services/<nome>_service.py      # lógica de negócio (check/delete/insert)
    templates/<nome>_query.py       # templates Jinja das queries SQL
  tests/
  .env.example                      # variáveis de ambiente exigidas, com valores de exemplo
  README.md                         # documentação local da camada (fonte de verdade primária)

terraform/modules/                  # módulos reutilizáveis: bigquery_table, cloud_run_job,
                                     # cloud_scheduler_http, secret_manager_secret
terraform/environments/dev/         # nenhum módulo instanciado ainda
terraform/environments/prod/        # idem — mesmos módulos que dev quando houver deploy

.gitlab-ci.yml                      # CI: lint (ruff bloqueante, mypy permissivo) + test
pyproject.toml, ruff.toml,          # configuração do workspace uv na raiz
.pre-commit-config.yaml, uv.lock
CLAUDE.md                           # contexto de negócio e de migração — leitura obrigatória
```

## Pré-requisitos

- Python 3.12 (ver `.python-version`)
- [`uv`](https://docs.astral.sh/uv/) — `pip install uv` ou `pipx install uv`
- Acesso ao projeto GCP correspondente ao ambiente (dev: `gglobo-billinghomolog-hdg-prd`;
  prod: `gglobo-billing-hdg-prd`) **apenas se for executar contra BigQuery real** — para rodar
  testes e lint localmente isso não é necessário, tudo é mockado.

## Como rodar localmente

Instalar todas as dependências do workspace (lib + pipelines) em um único ambiente:

```bash
uv sync --all-packages
```

Rodar toda a suíte de testes do workspace:

```bash
uv run pytest
```

Rodar testes de um pacote específico:

```bash
uv run pytest libs/billing_common/tests
uv run pytest pipelines/silver/tests
uv run pytest pipelines/gold_pre_foundation/tests
uv run pytest pipelines/gold_foundation/tests
uv run pytest pipelines/gold/tests
uv run pytest pipelines/unificado/tests
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

Executar uma camada manualmente contra BigQuery real (requer `.env` configurado e credenciais
GCP válidas — ver `docs/OPERACAO.md` para o passo a passo completo):

```bash
uv run python -m silver_pipeline.main 2024-04-01
```

## Como testar

Ver checklist completo em [`docs/ONBOARDING.md`](docs/ONBOARDING.md). Resumo: todos os testes
das 5 camadas do medalhão + `billing_common` usam mocks (`unittest.mock.patch`) — nenhum teste
hoje faz chamada real a BigQuery ou Secret Manager. As queries esperadas em
`tests/expected_*_queries.py` são geradas renderizando o template Jinja real de produção, não
strings copiadas à mão — isso garante que o teste nunca diverge do SQL real do pipeline.

## Como fazer deploy

**Estado real hoje**: não há Terraform nem pipeline de deploy automatizado para as 5 camadas do
medalhão (`silver`, `gold_pre_foundation`, `gold_foundation`, `gold`, `unificado`). Existem
módulos Terraform reutilizáveis em `terraform/modules/` (`bigquery_table`, `cloud_run_job`,
`cloud_scheduler_http`, `secret_manager_secret`), mas nenhum está instanciado em
`terraform/environments/{dev,prod}/` no momento.

Detalhe completo, comandos reais e o que está e não está em escopo:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

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
6. Adicionar um job `pytest-<nome>-pipeline` em `.gitlab-ci.yml` — hoje só `billing-common` e
   `silver-pipeline` têm job de teste dedicado no CI; as demais camadas migradas não são
   testadas automaticamente em pipeline.

## Workspace `uv`

A raiz define `[tool.uv.workspace] members = ["libs/*", "pipelines/*"]`. Todos os
`pyproject.toml` do workspace resolvem para um único `uv.lock` (versionado no git) —
não criar lockfiles individuais por pacote.

## CI

`.gitlab-ci.yml` define dois estágios: `lint` (ruff bloqueante, mypy permissivo) e `test`
(um job de pytest por pacote do workspace — hoje apenas `billing-common` e `silver-pipeline`
têm job dedicado). Ver o próprio arquivo para detalhes e `docs/DEPLOYMENT.md` para a lacuna de
cobertura nos demais pacotes.

## Documentação completa

| Documento | Conteúdo |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | Contexto de negócio, prioridades de migração, débitos técnicos do legado |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Arquitetura detalhada, diagramas, serviços externos reais |
| [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) | Origens, transformações, destinos, tabelas reais por camada |
| [`docs/ONBOARDING.md`](docs/ONBOARDING.md) | Onboarding, testes, FAQ para quem está entrando agora |
| [`docs/OPERACAO.md`](docs/OPERACAO.md) | Como executar/reprocessar cada camada manualmente |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Catálogo de problemas conhecidos e monitoramento |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Runbooks de incidente por cenário |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Processo de deploy real vs. fora de escopo |
| [`docs/TERRAFORM.md`](docs/TERRAFORM.md) | Terraform 101 — conceitos do zero, tour pelos módulos e comandos seguros para quem nunca usou Terraform |
