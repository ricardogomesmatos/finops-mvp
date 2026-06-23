"""Queries esperadas para os testes de `GoldService`.

Existe uma baseline de teste legado em
`gcp_labels/tests/test_gold_label_service.py` +
`gcp_labels/tests/expected_gold_queries.py`, mas confirmado por leitura que
ela está **desatualizada**: `expected_check_gold_query`/`expected_insert_gold_query`
legados leem diretamente da Silver via uma CTE `silver AS (...)`, enquanto o
`templates/gold_query.py` real (atual) lê de `tb_gcp_gold_pre_foundation` via
`rateios_gold AS (...)` e aplica rateio Foundation — o SQL mudou
significativamente desde que aquela baseline foi escrita.

Este módulo **renderiza o template atual** (a mesma fonte de verdade usada em
produção) com parâmetros fixos de teste, no mesmo espírito de
`pipelines/gold_pre_foundation/tests/expected_gold_pre_foundation_queries.py`.
"""

from __future__ import annotations

import jinja2
from gold_pipeline.templates.gold_query import (
    CHECK_GOLD_DATA,
    DELETE_GOLD_DATA,
    INSERT_GOLD_DATA,
    SELECT_GOLD_DATA,
)
from gold_pipeline.templates.lancamentos_looker_merge_query import LOOKER_MERGE_QUERY

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

INVOICE_MONTH = "2024-04-01"
PROJECT_ID = "gglobo-billinghomolog-hdg-prd"
GCP_GOLD_PRE_FOUNDATION_TABLE = "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation"
GCP_GOLD_FOUNDATION_DASHBOARD_TABLE = (
    "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_billing_foundation_labels_dashboard"
)
GCP_GOLD_TABLE = "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_billing_projeto_ar_label"
GCP_MARKETPLACE_SERVICES_TABLE = "gglobo-billing-hdg-prd.billing_raw.tb_gcp_marketplace_services"
CUSTO_UNITARIO_FIELDS = ["squad", "produto"]

EXPECTED_GENERATE_NULL_COLUMNS = (
    "IFNULL(squad, 'squad-nao-identificado') AS squad, "
    "IFNULL(produto, 'produto-nao-identificado') AS produto,"
)
EXPECTED_GENERATE_CUSTOM_COLUMNS = (
    "(SELECT value FROM z.custo_unitario WHERE key = 'squad') as squad, "
    "(SELECT value FROM z.custo_unitario WHERE key = 'produto') as produto,"
)

EXPECTED_SELECT_GOLD_DATA = _jinja_env.from_string(SELECT_GOLD_DATA).render(
    invoice_month=INVOICE_MONTH,
    gold_pre_foundation=GCP_GOLD_PRE_FOUNDATION_TABLE,
    gcp_marketplace_services_table=GCP_MARKETPLACE_SERVICES_TABLE,
    project_id=PROJECT_ID,
    gcp_billing_foundation_labels_dashboard=GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
)

EXPECTED_CHECK_GOLD_DATA = _jinja_env.from_string(CHECK_GOLD_DATA).render(
    invoice_month=INVOICE_MONTH,
    gold_pre_foundation=GCP_GOLD_PRE_FOUNDATION_TABLE,
    select_gold_data=EXPECTED_SELECT_GOLD_DATA,
    project_id=PROJECT_ID,
)

EXPECTED_DELETE_GOLD_DATA = _jinja_env.from_string(DELETE_GOLD_DATA).render(
    gcp_label_gold_table=GCP_GOLD_TABLE,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)

EXPECTED_INSERT_GOLD_DATA = _jinja_env.from_string(INSERT_GOLD_DATA).render(
    invoice_month=INVOICE_MONTH,
    select_gold_data=EXPECTED_SELECT_GOLD_DATA,
    final_table=GCP_GOLD_TABLE,
    project_id=PROJECT_ID,
)

EXPECTED_LOOKER_MERGE_QUERY = _jinja_env.from_string(LOOKER_MERGE_QUERY).render(
    invoice_month=INVOICE_MONTH,
    select_gold_data=EXPECTED_SELECT_GOLD_DATA,
    final_table=GCP_GOLD_TABLE,
    project_id=PROJECT_ID,
)
