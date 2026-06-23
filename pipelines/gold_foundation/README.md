# gold_foundation_pipeline

Camada Gold Foundation do medalhão moderno `gcp_labels`: aplica o rateio Foundation
sobre a Gold Pre-Foundation (`billing_gold.tb_gcp_gold_pre_foundation`), filtrando
projetos/serviços mapeados na planilha Foundation, classificando `ambiente`
(produção/QA/dev/POC/marketplace) e grava o resultado em duas tabelas:

- `billing_gold.tb_gcp_billing_foundation_labels` (tabela "linha a linha").
- `billing_gold.tb_gcp_billing_foundation_labels_dashboard` (agregada, consumida
  pelo dashboard Looker Studio, combinando a tabela acima com vistas de rateio
  Komodo/SRE e SMTP/Infra).

Migrado de `gcp_labels/services/gold_label_foundation_service.py` (legado), com
paridade funcional confirmada.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE`,
`GCP_GOLD_LABEL_FOUNDATION_TABLE`, `GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE`.

## Achados de paridade (preservados fielmente, não corrigidos nesta migração)

- **`bypass_validation` é um parâmetro órfão**: o construtor aceita
  `bypass_validation`, mas nunca o usa — esta camada não tem validação de custo
  (diferente de Gold Pre-Foundation e Gold). O orquestrador legado
  (`gcp_labels/main.py`) também nunca o passa ao instanciar o serviço.
- **Projeto hardcoded fora do `project_id` parametrizado**: o `INNER JOIN` de
  `INSERT_GOLD_FOUNDATION_DATA` lê
  `gglobo-billing-hdg-prd.billing_raw.sheets_gcp_projetos_servicos_foundation`
  sempre do projeto de produção, mesmo quando esta camada roda em homologação.
- **Nome de tabela hardcoded dessincronizável**: `INSERT_GOLD_FOUNDATION_DASHBOARD_DATA`
  lê de `{{project_id}}.billing_gold.tb_gcp_billing_foundation_labels` com o nome da
  tabela escrito literalmente no SQL, em vez de reutilizar
  `GCP_GOLD_LABEL_FOUNDATION_TABLE`. Se a env var mudar, esta leitura não acompanha.

## Uso

```python
from gold_foundation_pipeline.services.gold_foundation_service import GoldFoundationService

service = GoldFoundationService()
result = service.load_gold_foundation_data(invoice_month="2024-04-01")
```

Ou via entry point mínimo:

```bash
uv run python -m gold_foundation_pipeline.main 2024-04-01
```

## Testes

```bash
uv run pytest pipelines/gold_foundation/tests
```

Não existe baseline de teste legado para esta camada (`gcp_labels/tests/` só
cobre Silver e Gold). Os testes deste diretório renderizam o template SQL real
(`templates/gold_foundation_query.py`) com parâmetros fixos, no mesmo espírito de
`pipelines/gold_pre_foundation/tests/`.
