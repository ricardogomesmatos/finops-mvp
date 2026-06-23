"""Queries esperadas para os testes de `SilverLabelService`.

Reescrito do zero (não portado do legado) — ver `CLAUDE.md`/plano de migração
para o detalhe completo de por que `gcp_labels/tests/expected_silver_queries.py`
estava desatualizado em relação ao template de produção real:

1. Faltava a coluna `net_cost` (adicionada ao template depois que o teste legado
   foi escrito).
2. Usava `CONTAINS_SUBSTR` em vez de `REGEXP_CONTAINS` (mudança real de
   comportamento de match de labels, não cosmética).
3. Esperava partição `("2024-03-27", "2024-05-10")` para invoice_month
   "2024-04-01"; a fórmula atual (-17/+10 dias a partir do primeiro/último dia
   do mês) produz `("2024-03-15", "2024-05-10")`.

Em vez de colar manualmente o texto das queries renderizadas (risco de erro de
transcrição), este módulo **renderiza o template atual** (`templates/silver_query.py`,
a mesma fonte de verdade usada em produção) com os parâmetros fixos de teste —
garantindo que o "expected" nunca possa divergir do template real por
transcrição manual. Se o template mudar, estas constantes mudam automaticamente
na próxima execução dos testes, e qualquer divergência de comportamento real
fica visível nas asserções do `test_silver_label_service.py` (não aqui).
"""

from __future__ import annotations

import jinja2
from silver_pipeline.templates.silver_query import (
    CHECK_SILVER_DATA,
    DELETE_SILVER_DATA,
    INSERT_SILVER_DATA,
    SELECT_RAW_LABEL_DATA,
)

_jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

# Parâmetros fixos usados em todos os testes desta suíte.
INVOICE_MONTH = "2024-04-01"
PARTITION_START = "2024-03-15"
PARTITION_END = "2024-05-10"
PROJECT_ID = "gglobo-billinghomolog-hdg-prd"
GCP_SILVER_LABEL_TABLE = "gglobo-billinghomolog-hdg-prd.billing_silver.gcp_billing_silver_label"

EXPECTED_SELECT_RAW_LABEL_DATA = _jinja_env.from_string(SELECT_RAW_LABEL_DATA).render(
    invoice_month=INVOICE_MONTH,
    partition_start=PARTITION_START,
    partition_end=PARTITION_END,
    project_id=PROJECT_ID,
)

EXPECTED_CHECK_SILVER_DATA = _jinja_env.from_string(CHECK_SILVER_DATA).render(
    select_silver_data=EXPECTED_SELECT_RAW_LABEL_DATA,
    invoice_month=INVOICE_MONTH,
    partition_start=PARTITION_START,
    partition_end=PARTITION_END,
    project_id=PROJECT_ID,
)

EXPECTED_INSERT_SILVER_DATA = _jinja_env.from_string(INSERT_SILVER_DATA).render(
    select_silver_data=EXPECTED_SELECT_RAW_LABEL_DATA,
    gcp_silver_label_table=GCP_SILVER_LABEL_TABLE,
    project_id=PROJECT_ID,
)

EXPECTED_DELETE_SILVER_DATA = _jinja_env.from_string(DELETE_SILVER_DATA).render(
    gcp_silver_label_table=GCP_SILVER_LABEL_TABLE,
    invoice_month=INVOICE_MONTH,
    project_id=PROJECT_ID,
)
