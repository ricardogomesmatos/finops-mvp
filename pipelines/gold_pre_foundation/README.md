# gold_pre_foundation_pipeline

Camada Gold Pre-Foundation do medalhão moderno `gcp_labels`: aplica o pré-rateio sobre a
Silver com labels do GCP (`billing_silver.gcp_billing_silver_label`), unindo via `UNION ALL`
com views/tabelas de rateio externas (BQ, Cloud Armor, Databricks, alocação de créditos),
calcula `custo`/`creditos`/`credito_cud`/`ajuste`/`custo_suporte`/`credito_suporte`, resolve
dados de negócio (`cc`, `workstream`, `iniciativa`, hierarquia de centro de custo) e grava o
resultado em `billing_gold.tb_gcp_gold_pre_foundation`.

Migrado de `gcp_labels/services/gold_label_pre_foundation_service.py` (legado), com paridade
funcional confirmada. Ver `CLAUDE.md` na raiz do repositório para o contexto completo da
migração.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `GCP_SILVER_LABEL_TABLE`,
`GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE`, `GCP_MARKETPLACE_SERVICES_TABLE`,
`COST_VALIDATION_LIMIT`, `CUSTO_UNITARIO_FIELDS`.

**Nota sobre `CUSTO_UNITARIO_FIELDS`**: confirmado por leitura do template SQL real
(`templates/gold_pre_foundation_query.py`) que os parâmetros Jinja derivados desta variável
(`custo_unitario_column_names`/`generate_null_columns`) não são referenciados em nenhuma das
4 queries da camada hoje. Aparentam ser código órfão do legado (talvez de uma versão anterior
do SQL). Mantido fielmente por paridade comportamental — não removido nesta migração.

## Dependências externas fora de escopo

O `SELECT` principal desta camada consome, via `UNION ALL`, views/tabelas que **não foram
migradas** nesta entrega (continuam sendo lidas via SQL, apenas referenciadas):

- `billing_gold.vw_gcp_rateio_bq_labels`
- `billing_gold.vw_gcp_rateio_bq_labels_v2`
- `billing_gold.vw_gcp_rateio_armor_fee_label`
- `billing_gold.vw_gcp_rateio_databricks_labels`
- `billing_gold.tb_alocacao_creditos_migration-1-1747074799001`

Também há hardcode de correção financeira para `invoice_month = '2023-12-01'` (erro histórico
de cobrança da GCP, documentado em comentário no SQL) — replicado literalmente.

## Uso

```python
from gold_pre_foundation_pipeline.services.gold_pre_foundation_service import (
    GoldPreFoundationService,
)

service = GoldPreFoundationService(bypass_validation=False)
result = service.load_gold_pre_foundation_data(invoice_month="2024-04-01")
```

Ou via entry point mínimo:

```bash
uv run python -m gold_pre_foundation_pipeline.main 2024-04-01
```

## Testes

```bash
uv run pytest pipelines/gold_pre_foundation/tests
```

Os testes não fazem chamadas reais ao BigQuery — `BigQueryAdapter` é mockado via
`unittest.mock.patch`. `expected_gold_pre_foundation_queries.py` é gerado renderizando o
template atual (`templates/gold_pre_foundation_query.py`) com os parâmetros de teste,
garantindo que a query esperada nunca diverge do template de produção real.

Não existe baseline de teste legado utilizável para esta camada específica: os testes em
`gcp_labels/tests/test_gold_label_service.py`/`expected_gold_queries.py` testam
`GCPGoldLabelService` (camada Gold seguinte) e importam de `templates.gold_query`, não de
`gold_pre_foundation_query`. Os testes deste diretório foram escritos do zero contra o
comportamento real do service + template legados.
