"""Queries esperadas para os testes de `UnificadoService`.

Não existe baseline de teste legado para esta camada (`gcp_labels/tests/` só
cobre Silver e Gold). Este módulo **renderiza o template atual**
(`templates/gold_unificada_query.py`, a mesma fonte de verdade usada em
produção) com parâmetros fixos de teste, no mesmo espírito de
`pipelines/gold_pre_foundation/tests/expected_gold_pre_foundation_queries.py`.
"""

from __future__ import annotations

import jinja2
from unificado_pipeline.templates.gold_unificada_query import (
    CHECK_GOLD_UNIFICADO_DATA,
    DELETE_GOLD_UNIFICADO_DATA,
    INSERT_GOLD_UNIFICADO_DATA,
    SELECT_GOLD_UNIFICADO_DATA,
)

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

INVOICE_MONTH = "2024-04-01"
PROJECT_ID = "gglobo-billinghomolog-hdg-prd"
GCP_GOLD_UNIFICADO_TABLE = (
    "gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_tsuru_dbaas_unificada_labels"
)

EXPECTED_SELECT_GOLD_UNIFICADO_DATA = _jinja_env.from_string(SELECT_GOLD_UNIFICADO_DATA).render(
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)

EXPECTED_DELETE_GOLD_UNIFICADO_DATA = _jinja_env.from_string(DELETE_GOLD_UNIFICADO_DATA).render(
    gcp_gold_unificado_label_table=GCP_GOLD_UNIFICADO_TABLE,
    invoice_month=INVOICE_MONTH,
)

EXPECTED_INSERT_GOLD_UNIFICADO_DATA = _jinja_env.from_string(INSERT_GOLD_UNIFICADO_DATA).render(
    gcp_gold_unificado_label_table=GCP_GOLD_UNIFICADO_TABLE,
    invoice_month=INVOICE_MONTH,
    select_gold_unificado_query=EXPECTED_SELECT_GOLD_UNIFICADO_DATA,
)

EXPECTED_CHECK_GOLD_UNIFICADO_DATA = _jinja_env.from_string(CHECK_GOLD_UNIFICADO_DATA).render(
    select_gold_unificado_query=EXPECTED_SELECT_GOLD_UNIFICADO_DATA,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)
