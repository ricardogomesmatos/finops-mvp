"""SQL de merge de lançamentos manuais via Looker, migrado literalmente de
`gcp_labels/templates/lancamentos_looker_merge_query.py` (legado).

Achado de paridade preservado: a tabela de destino (`T`) é a tabela final
`tb_gcp_billing_projeto_ar_label` com o nome do projeto/dataset hardcoded
(`gglobo-billing-hdg-prd`) no `FROM` da subquery `S`, mesmo quando esta camada
roda em homologação — diferente do `final_table` parametrizado usado em
`INSERT_GOLD_DATA`. Replicado fielmente, não corrigido.
"""

from __future__ import annotations

LOOKER_MERGE_QUERY = """
MERGE
  `{{project_id}}.billing_gold.tb_gcp_billing_projeto_ar_label` AS T
USING
  (
  SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    iniciativa,
    workstream,
    projeto_id,
    projeto,
    servico_nome,
    servico_id,
    sku_description,
    currency_conversion_rate,
    -- Replaces resource_global_name in the key
    'manual_input' sku_id,
    labels_string,
    tags_string,
    system_labels_string,
    resource_name,
    resource_global_name,
    custo,
    creditos,
    credito_cud,
    ajuste,
    custo_suporte,
    credito_suporte,
    custo_foundation,
    credito_foundation,
    cud_foundation,
    diretoria_n1,
    diretoria,
    gerencia_lider,
    responsavel_gerencial,
    area,
    resource_id,
    cc_nome,
    cc_codigo
  FROM
    `gglobo-billing-hdg-prd.billing_gold.vw_lancamentos_looker` ) AS S
ON
  T.billing_account_id = S.billing_account_id
  AND T.usage_date = S.usage_date
  AND t.sku_description = S.sku_description
  AND T.sku_id = S.sku_id
  AND T.currency_conversion_rate = S.currency_conversion_rate  -- Key adjustment
  WHEN NOT MATCHED
  THEN
INSERT
  ( billing_account_id,
    usage_date,
    invoice_month,
    iniciativa,
    workstream,
    projeto_id,
    projeto,
    servico_nome,
    servico_id,
    sku_description,
    currency_conversion_rate,
    sku_id,
    resource_name,
    resource_global_name,
    custo,
    creditos,
    credito_cud,
    ajuste,
    custo_suporte,
    credito_suporte,
    custo_foundation,
    credito_foundation,
    cud_foundation,
    diretoria_n1,
    diretoria_n2,
    gerencia_n3,
    gestor,
    area_n4,
    resource_id,
    cc_nome,
    cc_codigo )
VALUES
  ( S.billing_account_id,
    S.usage_date,
    S.invoice_month,
    S.iniciativa,
    S.workstream,
    S.projeto_id,
    S.projeto,
    S.servico_nome,
    S.servico_id,
    S.sku_description,
    S.currency_conversion_rate,
    S.sku_id,
    S.resource_name,
    S.resource_global_name,
    S.custo,
    S.creditos,
    S.credito_cud,
    S.ajuste,
    S.custo_suporte,
    S.credito_suporte,
    S.custo_foundation,
    S.credito_foundation,
    S.cud_foundation,
    S.diretoria_n1,
    S.diretoria,
    S.gerencia_lider,
    S.responsavel_gerencial,
    S.area,
    S.resource_id,
    S.cc_nome,
    S.cc_codigo );"""
