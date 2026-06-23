# silver_pipeline

Camada Silver do medalhão moderno `gcp_labels`: aplica labels de negócio (squad/produto)
sobre o billing raw do GCP, valida paridade de custo entre raw e silver, e grava o
resultado em `billing_silver.gcp_billing_silver_label`.

Migrado de `gcp_labels/services/silver_label_service.py` (legado), com paridade funcional
confirmada. Ver `CLAUDE.md` na raiz do repositório para o contexto completo da migração.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `GCP_SILVER_LABEL_TABLE`, `COST_VALIDATION_LIMIT`.

## Uso

```python
from silver_pipeline.services.silver_label_service import SilverLabelService

service = SilverLabelService(bypass_validation=False)
result = service.load_silver_data(invoice_month="2024-04-01")
```

Ou via entry point mínimo:

```bash
uv run python -m silver_pipeline.main 2024-04-01
```

## Testes

```bash
uv run pytest pipelines/silver/tests
```

Os testes não fazem chamadas reais ao BigQuery — `BigQueryAdapter` é mockado via
`unittest.mock.patch`. `expected_silver_queries.py` é gerado renderizando o template atual
(`templates/silver_query.py`) com os parâmetros de teste, garantindo que a query esperada
nunca diverge do template de produção real.
