"""Queries esperadas para os testes de `GoldPreFoundationService`.

Não existe baseline de teste legado utilizável para esta camada: confirmado
por leitura de `gcp_labels/tests/test_gold_label_service.py` e
`expected_gold_queries.py` que ambos testam `GCPGoldLabelService` (camada
Gold, não Gold Pre-Foundation) e importam de `templates.gold_query`, não de
`gold_pre_foundation_query`. Os testes legados naquele caminho são, na
prática, testes (desatualizados) da camada seguinte do medalhão — não desta.

Este módulo **renderiza o template atual**
(`templates/gold_pre_foundation_query.py`, a mesma fonte de verdade usada em
produção) com parâmetros fixos de teste, no mesmo espírito de
`pipelines/silver/tests/expected_silver_queries.py` — garantindo que o
"expected" nunca possa divergir do template real por transcrição manual.
"""

from __future__ import annotations

import jinja2
from gold_pre_foundation_pipeline.templates.gold_pre_foundation_query import (
    CHECK_GOLD_PRE_FOUNDATION_DATA,
    DELETE_GOLD_PRE_FOUNDATION_DATA,
    INSERT_GOLD_PRE_FOUNDATION_DATA,
    SELECT_GOLD_PRE_FOUNDATION_DATA,
)

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

# Parâmetros fixos usados em todos os testes desta suíte.
INVOICE_MONTH = "2024-04-01"
PROJECT_ID = "gglobo-billinghomolog-hdg-prd"
GCP_SILVER_LABEL_TABLE = "gglobo-billinghomolog-hdg-prd.billing_silver.gcp_billing_silver_label"
GCP_GOLD_PRE_FOUNDATION_TABLE = "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation"
GCP_MARKETPLACE_SERVICES_TABLE = "gglobo-billinghomolog-hdg-prd.billing_raw.tb_gcp_marketplace_services"
CUSTO_UNITARIO_FIELDS = ["squad", "produto"]

EXPECTED_CUSTO_UNITARIO_COLUMN_NAMES = ", ".join(CUSTO_UNITARIO_FIELDS)
# `generate_null_columns`/`generate_custom_columns` só fazem `.rstrip()` (remove
# espaço em branco), não removem a vírgula final de cada item concatenado.
EXPECTED_GENERATE_NULL_COLUMNS = (
    "IFNULL(squad, 'squad-nao-identificado') AS squad, "
    "IFNULL(produto, 'produto-nao-identificado') AS produto,"
)
EXPECTED_GENERATE_CUSTOM_COLUMNS = (
    "(SELECT value FROM z.custo_unitario WHERE key = 'squad') as squad, "
    "(SELECT value FROM z.custo_unitario WHERE key = 'produto') as produto,"
)

EXPECTED_SELECT_GOLD_PRE_FOUNDATION_DATA = _jinja_env.from_string(
    SELECT_GOLD_PRE_FOUNDATION_DATA
).render(
    invoice_month=INVOICE_MONTH,
    gcp_billing_silver=GCP_SILVER_LABEL_TABLE,
    gcp_marketplace_services_table=GCP_MARKETPLACE_SERVICES_TABLE,
    custo_unitario_column_names=EXPECTED_CUSTO_UNITARIO_COLUMN_NAMES,
    generate_null_columns=EXPECTED_GENERATE_NULL_COLUMNS,
    project_id=PROJECT_ID,
)

EXPECTED_CHECK_GOLD_PRE_FOUNDATION_DATA = _jinja_env.from_string(
    CHECK_GOLD_PRE_FOUNDATION_DATA
).render(
    invoice_month=INVOICE_MONTH,
    gcp_billing_silver=GCP_SILVER_LABEL_TABLE,
    select_gold_pre_foundation_data=EXPECTED_SELECT_GOLD_PRE_FOUNDATION_DATA,
    project_id=PROJECT_ID,
)

EXPECTED_DELETE_GOLD_PRE_FOUNDATION_DATA = _jinja_env.from_string(
    DELETE_GOLD_PRE_FOUNDATION_DATA
).render(
    gcp_label_gold_pre_foundation_table=GCP_GOLD_PRE_FOUNDATION_TABLE,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)

EXPECTED_INSERT_GOLD_PRE_FOUNDATION_DATA = _jinja_env.from_string(
    INSERT_GOLD_PRE_FOUNDATION_DATA
).render(
    invoice_month=INVOICE_MONTH,
    custo_unitario_column_names=EXPECTED_GENERATE_CUSTOM_COLUMNS,
    select_gold_pre_foundation_data=EXPECTED_SELECT_GOLD_PRE_FOUNDATION_DATA,
    final_table=GCP_GOLD_PRE_FOUNDATION_TABLE,
    project_id=PROJECT_ID,
)
