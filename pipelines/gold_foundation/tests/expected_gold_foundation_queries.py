"""Queries esperadas para os testes de `GoldFoundationService`.

Não existe baseline de teste legado para esta camada (`gcp_labels/tests/` só
cobre Silver e Gold). Este módulo **renderiza o template atual**
(`templates/gold_foundation_query.py`, a mesma fonte de verdade usada em
produção) com parâmetros fixos de teste, no mesmo espírito de
`pipelines/gold_pre_foundation/tests/expected_gold_pre_foundation_queries.py`.
"""

from __future__ import annotations

import jinja2
from gold_foundation_pipeline.templates.gold_foundation_query import (
    DELETE_GOLD_FOUNDATION_DATA,
    INSERT_GOLD_FOUNDATION_DASHBOARD_DATA,
    INSERT_GOLD_FOUNDATION_DATA,
)

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

INVOICE_MONTH = "2024-04-01"
PROJECT_ID = "gglobo-billinghomolog-hdg-prd"
GCP_GOLD_PRE_FOUNDATION_TABLE = "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation"
GCP_GOLD_FOUNDATION_TABLE = "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_billing_foundation_labels"
GCP_GOLD_FOUNDATION_DASHBOARD_TABLE = (
    "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_billing_foundation_labels_dashboard"
)

EXPECTED_DELETE_GOLD_FOUNDATION_DATA = _jinja_env.from_string(DELETE_GOLD_FOUNDATION_DATA).render(
    target_table=GCP_GOLD_FOUNDATION_TABLE,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)

EXPECTED_DELETE_GOLD_FOUNDATION_DASHBOARD_DATA = _jinja_env.from_string(
    DELETE_GOLD_FOUNDATION_DATA
).render(
    target_table=GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)

EXPECTED_INSERT_GOLD_FOUNDATION_DATA = _jinja_env.from_string(INSERT_GOLD_FOUNDATION_DATA).render(
    invoice_month=INVOICE_MONTH,
    gcp_gold_label_foundation_table=GCP_GOLD_FOUNDATION_TABLE,
    project_id=PROJECT_ID,
    gold_pre_foundation_table=GCP_GOLD_PRE_FOUNDATION_TABLE,
)

EXPECTED_INSERT_GOLD_FOUNDATION_DASHBOARD_DATA = _jinja_env.from_string(
    INSERT_GOLD_FOUNDATION_DASHBOARD_DATA
).render(
    invoice_month=INVOICE_MONTH,
    gcp_gold_label_foundation_dashboard_table=GCP_GOLD_FOUNDATION_DASHBOARD_TABLE,
    project_id=PROJECT_ID,
)
