# gold_pipeline

Camada Gold do medalhão moderno `gcp_labels`: lê a Gold Pre-Foundation
(`billing_gold.tb_gcp_gold_pre_foundation`), aplica o rateio Foundation
(`custo_foundation`/`credito_foundation`/`cud_foundation`, calculado
proporcionalmente ao total da Gold Foundation Dashboard), valida paridade de
custo contra a Gold Pre-Foundation e grava em
`billing_gold.tb_gcp_billing_projeto_ar_label`. Em seguida, faz `MERGE` de
lançamentos manuais via Looker (`vw_lancamentos_looker`) e roda um backup de
pesos de rateio de slots de BigQuery fora da org.

Migrado de `gcp_labels/services/gold_label_service.py` (legado), com paridade
funcional confirmada.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE`,
`GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE`, `GCP_GOLD_LABEL_TABLE`,
`GCP_MARKETPLACE_SERVICES_TABLE`, `COST_VALIDATION_LIMIT`, `CUSTO_UNITARIO_FIELDS`.

## Achados de paridade (preservados fielmente, não corrigidos nesta migração)

- **`CUSTO_UNITARIO_FIELDS` é código órfão**: `generate_custom_columns`/
  `generate_null_columns` existem no service mas não são chamados em
  `load_gold_data` — mesmo achado já documentado em `gold_pre_foundation`.
- **`backup_rateio_bq_valiant` roda incondicionalmente** ao final de
  `load_gold_data`, escrevendo numa tabela fixa de projeto de produção
  (`gglobo-billing-hdg-prd.billing_gold.backup_rateio_bq_slots_fora_org`),
  mesmo quando a camada roda em homologação.
- **`LOOKER_MERGE_QUERY` lê e escreve em tabelas hardcoded de produção**
  (`gglobo-billing-hdg-prd`), independentemente do `project_id` configurado —
  diferente do `final_table` parametrizado usado em `INSERT_GOLD_DATA`.
- **Baseline de teste legado desatualizada**: `gcp_labels/tests/test_gold_label_service.py`
  + `expected_gold_queries.py` testam uma versão antiga de `SELECT_GOLD_DATA`
  que lia diretamente da Silver via CTE — o template atual lê de
  `tb_gcp_gold_pre_foundation` e aplica rateio Foundation. Os testes deste
  pipeline renderizam o template real atual (ver
  `tests/expected_gold_queries.py`), não a baseline legada.

## Dependências externas fora de escopo

`SELECT_GOLD_DATA` consome, via `LEFT JOIN`, tabelas/views que **não foram
migradas** nesta entrega: `billing_raw.sheets_gcp_projetos_servicos_foundation`,
`billing_raw.tb_gcp_marketplace_services`, `billing_raw.gcp_foundation_raw`,
`billing_gold.vw_gcp_komodo_labels`, `billing_gold.vw_gcp_smtp_labels`. O
`LOOKER_MERGE_QUERY` consome `billing_gold.vw_lancamentos_looker`.

## Uso

```python
from gold_pipeline.services.gold_service import GoldService

service = GoldService(bypass_validation=False)
result = service.load_gold_data(invoice_month="2024-04-01")
```

Ou via entry point mínimo:

```bash
uv run python -m gold_pipeline.main 2024-04-01
```

## Testes

```bash
uv run pytest pipelines/gold/tests
```
