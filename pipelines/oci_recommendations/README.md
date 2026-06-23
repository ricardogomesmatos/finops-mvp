# oci_recommendations_pipeline

Extração das recomendações de otimização da OCI (serviço Optimizer/Cloud Advisor)
para `billing_raw.tb_oci_optimizer_recommendations_snapshot` no BigQuery.

Camada estritamente raw/landing — sem transformação, dedup ou upsert. Cada
execução grava um snapshot append-only das recomendações ativas no momento,
particionado por `extracted_at`. Fases seguintes (transformação, alertas) são
tratadas em outro card.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `OCI_RECOMMENDATIONS_TABLE`,
`OCI_TENANCY_ID`, `OCI_CREDENTIALS_SECRET_ID`.

`OCI_CREDENTIALS_SECRET_ID` aponta para um secret no Secret Manager (não o
valor) com o payload JSON `{"user", "fingerprint", "tenancy", "region", "key_content"}`
— credenciais de API Key da OCI (não há Instance Principal disponível rodando
em Cloud Run no GCP).

## Uso

```python
from oci_recommendations_pipeline.services.oci_recommendations_service import (
    OciRecommendationsService,
)

service = OciRecommendationsService()
result = service.extract_and_load()
```

Ou via entry point do Cloud Run Job:

```bash
uv run python -m oci_recommendations_pipeline.main
```

## Testes

```bash
uv run pytest pipelines/oci_recommendations/tests
```

Nunca instancia o SDK `oci` nem o Secret Manager reais — `OptimizerClient`,
`list_call_get_all_results` e `get_secret_json` são mockados via
`unittest.mock.patch`, mesmo padrão usado em `pipelines/silver`.
