# billing_common

Biblioteca interna compartilhada por todos os pipelines do `finops-billing`. Substitui as
cópias duplicadas de `utils/logger.py`, `utils/env_configs.py`, `utils/date.py` e
`adapters/bigquery_adapter.py` que existiam em cada Cloud Function do ambiente legado
(`gcp-billing`).

## Módulos

- `billing_common.adapters.bigquery.BigQueryAdapter` — client de BigQuery unificado
  (DDL + execução de query com labels de custo por job).
- `billing_common.logging.json_logger.build_logger` — logger estruturado em JSON,
  compatível nativamente com Cloud Logging.
- `billing_common.config.base.BaseEnvConfigs` — validação de variáveis de ambiente
  obrigatórias; cada pipeline cria uma subclasse com sua própria lista.
- `billing_common.dates.date_util.DateUtil` — utilitários de data (primeiro/último dia
  do mês, mês anterior, meses em um intervalo).

## Uso em um pipeline

No `pyproject.toml` do pipeline:

```toml
[tool.uv.sources]
billing-common = { workspace = true }
```

No código:

```python
from billing_common.adapters.bigquery import BigQueryAdapter
from billing_common.config.base import BaseEnvConfigs
from billing_common.dates.date_util import DateUtil
from billing_common.logging.json_logger import build_logger
```

## Testes

```bash
uv run pytest libs/billing_common/tests
```
