"""SQL da camada Gold Pre-Foundation, migrado literalmente de
`gcp_labels/templates/gold_pre_foundation_query.py` (legado).

Fonte de verdade do negócio — não simplificar, corrigir ou "limpar" nada aqui
nesta entrega. Qualquer correção de comportamento é decisão pós-reconciliação
(`qa-reconciliation`), não desta migração.

Observações importantes confirmadas por leitura do legado (ver relatório de
migração para o detalhe completo):

1. Esta camada lê da Silver COM LABELS (`gcp_billing_silver_label`, parâmetro
   `gcp_billing_silver`/`GCP_SILVER_LABEL_TABLE`), nunca da `gcp_billing_silver`
   sem label.
2. O `SELECT_GOLD_PRE_FOUNDATION_DATA` faz UNION ALL da Silver com 4 views de
   rateio externas (`vw_gcp_rateio_bq_labels`, `vw_gcp_rateio_bq_labels_v2`,
   `vw_gcp_rateio_armor_fee_label`, `vw_gcp_rateio_databricks_labels`) e uma
   tabela fixa de alocação de créditos
   (`tb_alocacao_creditos_migration-1-1747074799001`), todas fora de escopo
   desta migração — apenas referenciadas via SQL, não migradas.
3. Há um hardcode de correção financeira para `invoice_month = '2023-12-01'`,
   documentado em comentário no próprio SQL, por causa de um erro histórico de
   cobrança da GCP que não seria corrigido por eles. Replicado literalmente —
   é uma correção financeira real, não decisão de design desta migração.
4. **Achado de código órfão**: o service legado monta os parâmetros Jinja
   `custo_unitario_column_names` (via `', '.join(...)`, usado em
   `select_gold_pre_foundation_data`) e `generate_null_columns` (saída de
   `generate_null_columns()`) e os injeta no render de
   `SELECT_GOLD_PRE_FOUNDATION_DATA`. Nenhum desses dois placeholders
   (`{{custo_unitario_column_names}}` / `{{generate_null_columns}}`) aparece no
   corpo de `SELECT_GOLD_PRE_FOUNDATION_DATA` abaixo — confirmado por leitura
   integral das 4 queries. Ou seja, a env var `CUSTO_UNITARIO_FIELDS` e os
   métodos `generate_custom_columns`/`generate_null_columns` do service
   produzem valores que hoje não têm efeito no SQL renderizado desta camada.
   Mantido fiel ao comportamento real (os parâmetros continuam sendo montados
   e passados ao `render()`, sem efeito), pois o objetivo desta migração é
   paridade comportamental — não corrigir o legado. Ver relatório de migração.
"""

from __future__ import annotations

SELECT_GOLD_PRE_FOUNDATION_DATA = """
WITH
silver AS (
  (
    SELECT
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2024-04-23') THEN DATE('2024-02-15') ELSE usage_date END AS usage_date,
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2024-04-23') THEN DATE('2024-02-01') ELSE z.invoice_month END AS invoice_month,
      billing_account_id,
      CASE
        WHEN service_description = 'Invoice' AND usage_date IN ('2023-06-02') THEN "gglobo-wm-user-profile-hdg-prd"
        WHEN service_description = 'Invoice' AND usage_date IN ('2023-12-06') THEN "gglobo-ims-globo-mda-poc"
        WHEN service_description = 'Invoice' AND usage_date IN ('2024-04-23') THEN "gglobo-liveproduction-mda-prd"
        WHEN service_description = 'Invoice' AND usage_date IN ('2024-06-01') AND adjustment_info_description = 'Gemini 1.5 API | 01C233-D025C4-615139 | Goodwill' THEN "gglobo-dotim-hdg-dev"
        ELSE project_id
      END AS project_id,
      CASE
        WHEN service_description = 'Invoice' AND usage_date IN ('2023-06-02') THEN "gglobo-wm-user-profile-hdg-prd"
        WHEN service_description = 'Invoice' AND usage_date IN ('2023-12-06') THEN "gglobo-ims-globo-mda-poc"
        WHEN service_description = 'Invoice' AND usage_date IN ('2024-04-23') THEN "gglobo-liveproduction-mda-prd"
        WHEN service_description = 'Invoice' AND usage_date IN ('2024-06-01') AND adjustment_info_description = 'Gemini 1.5 API | 01C233-D025C4-615139 | Goodwill' THEN "gglobo-dotim-hdg-dev"
        ELSE project_id
      END AS project_name,
      service_id,
      CASE
            WHEN service_description = 'Invoice' AND usage_date IN ('2023-01-11', '2023-01-12', '2023-01-26', '2023-02-01', '2023-03-29') THEN "Invoice - GCP AJUSTE ERRO"
            WHEN service_description = 'Invoice' AND usage_date IN ('2024-06-01') AND adjustment_info_type = 'GENERAL_ADJUSTMENT' THEN 'Support'
            ELSE z.service_description
      END AS service_description,
      sku_id, sku_description, currency_conversion_rate,
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2023-01-11', '2023-01-12', '2023-01-26', '2023-02-01', '2023-03-29') THEN 0 ELSE z.cost END AS cost,
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2023-01-11', '2023-01-12', '2023-01-26', '2023-02-01', '2023-03-29') THEN 0 ELSE z.net_cost END AS net_cost,
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2023-01-11', '2023-01-12', '2023-01-26', '2023-02-01', '2023-03-29') THEN z.cost ELSE z.credits_amount END AS credits_amount,
      CASE WHEN service_description = 'Invoice' AND usage_date IN ('2023-01-11', '2023-01-12', '2023-01-26', '2023-02-01', '2023-03-29') THEN "GCP AJUSTE ERRO" ELSE credits_type END AS credits_type,
      labels_string,
      tags_string,
      system_labels_string,
      resource_name,
      resource_global_name,
      usage_amount_in_pricing_units,
      usage_pricing_unit,
      consumption_model_description,
      price_effective_price_default,
      price_effective_price,
      price_pricing_unit_quantity
    FROM `{{gcp_billing_silver}}` z
    WHERE z.invoice_month = '{{invoice_month}}'
    -- Remove unwanted SKUs / credits
    AND NOT (
        IFNULL(sku_description, '') = 'Analysis Slots Attribution'
        OR sku_id = 'EFB7-4299-A2EC'
        OR credits_id IN (
            'migration-credit-1-1689795008681',
            '4f14ff69-74b4-41a2-a119-28d6920446a9_credit:0'
        )
    )
    -- Remove specific BigQuery Enterprise rows from internal billing projects
    AND NOT (
        project_id IN ('gglobo-billing-hdg-prd', 'valiant-circuit-129220')
        AND sku_description LIKE 'BigQuery Enterprise%'
        AND usage_date >= '2023-07-04'
    )
    -- Remove internal projects from 2024-09 forward
    AND NOT (
        (IFNULL(project_id, '') = 'pr-2e92731d148cb2cb'
        OR IFNULL(service_id, '') = '22A5-0D56-8786')
        AND invoice_month >= '2024-09-01'
    )
    AND credits_id <> 'a834e65f-3a14-4bf0-8ac8-893954cabcf4' --Referente ao card FLDFO-1940

    UNION ALL -- União que altera os créditos recebidos no 'credits_id' para ajustes

    SELECT
      usage_date, invoice_month,
      billing_account_id,
      project_id,
      project_name,
      service_id,
      'Invoice' AS service_description,
      CASE WHEN credits_id = '4f14ff69-74b4-41a2-a119-28d6920446a9_credit:0' THEN '3EF3-4E7E-B769' ELSE sku_id END AS sku_id,
      CASE WHEN credits_id = '4f14ff69-74b4-41a2-a119-28d6920446a9_credit:0' THEN 'Networking Cloud Armor Managed Protection Plus: Protected Resource' ELSE sku_description END AS sku_description,
      currency_conversion_rate,
      credits_amount AS cost,
      credits_amount AS net_cost,
      0.0 AS credits_amount,
      '' AS credits_type,
      labels_string,
      tags_string,
      system_labels_string,
      resource_name,
      resource_global_name,
      usage_amount_in_pricing_units,
      usage_pricing_unit,
      consumption_model_description,
      price_effective_price_default,
      price_effective_price,
      price_pricing_unit_quantity
    FROM `{{gcp_billing_silver}}` z
    WHERE invoice_month = '{{invoice_month}}'
    AND credits_id IN ('migration-credit-1-1689795008681', '4f14ff69-74b4-41a2-a119-28d6920446a9_credit:0')
  )
  UNION ALL
  (
    SELECT
      usage_date, invoice_month,
      billing_account_id,
      project_id, project_id AS project_name,
      servico_id, servico_nome,
      sku_id, sku_description, currency_conversion_rate,
      custo,
      0.0 AS net_cost,
      credito AS credits_amount,
      '' AS credits_type,
      labels_string,
      CAST(NULL AS STRING) AS tags_string,
      CAST(NULL AS STRING) AS system_labels_string,
      CAST(NULL AS STRING) AS resource_name,
      CAST(NULL AS STRING) AS resource_global_name,
      CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
      CAST(NULL AS STRING) AS usage_pricing_unit,
      NULL AS consumption_model_description,
      NULL AS price_effective_price_default,
      NULL AS price_effective_price,
      NULL AS price_pricing_unit_quantity
    FROM `{{project_id}}.billing_gold.vw_gcp_rateio_bq_labels`
    WHERE invoice_month = '{{invoice_month}}'
    AND invoice_month <= '2026-02-01'
  )
  UNION ALL
  (
    SELECT
      usage_date, invoice_month,
      billing_account_id,
      project_id, project_id AS project_name,
      servico_id, servico_nome,
      sku_id, sku_description, currency_conversion_rate,
      custo,
      0.0 AS net_cost,
      credito AS credits_amount,
      '' AS credits_type,
      labels_string,
      tags_string,
      system_labels_string,
      resource_name,
      resource_global_name,
      usage_amount_in_pricing_units,
      usage_pricing_unit,
      consumption_model_description,
      price_effective_price_default,
      price_effective_price,
      price_pricing_unit_quantity
    FROM `{{project_id}}.billing_gold.vw_gcp_rateio_bq_labels_v2`
    WHERE invoice_month = '{{invoice_month}}'
  )
  UNION ALL
  (
    SELECT
      usage_date, invoice_month,
      billing_account_id,
      project_id, project_name,
      service_id AS servico_id, service_description AS servico_nome,
      sku_id, sku_description, currency_conversion_rate,
      custo_rateado AS custo,
      0.0 AS net_cost,
      credito_rateado AS credits_amount,
      CASE WHEN credito_rateado != .0 THEN 'PROMOTION' ELSE '' END AS credits_type,
      CAST(NULL AS STRING) AS labels_string,
      CAST(NULL AS STRING) AS tags_string,
      CAST(NULL AS STRING) AS system_labels_string,
      CAST(NULL AS STRING) AS resource_name,
      CAST(NULL AS STRING) AS resource_global_name,
      CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
      CAST(NULL AS STRING) AS usage_pricing_unit,
      NULL AS consumption_model_description,
      NULL AS price_effective_price_default,
      NULL AS price_effective_price,
      NULL AS price_pricing_unit_quantity
    FROM `{{project_id}}.billing_gold.vw_gcp_rateio_armor_fee_label`
    WHERE invoice_month = '{{invoice_month}}'
  )
  UNION ALL
  (
    SELECT
      usage_date, invoice_month,
      billing_account_id,
      projeto_id AS project_id,
      projeto_id AS project_name,
      servico_id,
      servico_nome,
      sku_id,
      sku_description,
      0 AS currency_conversion_rate,
      custo,
      0.0 AS net_cost,
      creditos AS credits_amount,
      '' AS credits_type,
      CAST(NULL AS STRING) AS labels_string,
      CAST(NULL AS STRING) AS tags_string,
      CAST(NULL AS STRING) AS system_labels_string,
      CAST(NULL AS STRING) AS resource_name,
      CAST(NULL AS STRING) AS resource_global_name,
      CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
      CAST(NULL AS STRING) AS usage_pricing_unit,
      NULL AS consumption_model_description,
      NULL AS price_effective_price_default,
      NULL AS price_effective_price,
      NULL AS price_pricing_unit_quantity
      FROM `{{project_id}}.billing_gold.vw_gcp_rateio_databricks_labels`
    WHERE invoice_month = '{{invoice_month}}'
  )
  --Referente ao card FLDFO-1940
  UNION ALL
  (
    SELECT
    usage_date, invoice_month,
    billing_account_id,
    project_id,
    project_id as project_name,
    servico_id,
    servico_nome,
    NULL as sku_id, sku_description,
    0 as currency_conversion_rate,
    0 as custo,
    0.0 AS net_cost,
    credito as credits_amount,
    '' AS credits_type,
    CAST(NULL AS STRING) AS labels_string,
    CAST(NULL AS STRING) AS tags_string,
    CAST(NULL AS STRING) AS system_labels_string,
    CAST(NULL AS STRING) AS resource_name,
    CAST(NULL AS STRING) AS resource_global_name,
    CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
    CAST(NULL AS STRING) AS usage_pricing_unit,
    NULL AS consumption_model_description,
    NULL AS price_effective_price_default,
    NULL AS price_effective_price,
    NULL AS price_pricing_unit_quantity
    FROM `gglobo-billing-hdg-prd.billing_gold.tb_alocacao_creditos_migration-1-1747074799001`
    WHERE invoice_month = '{{invoice_month}}'
  )
), gold_pre_foundation AS (
-- ajuste para dezembro de 2023 devido a um erro de cobranca da GCP que nao sera corrigido por eles
    SELECT *
    FROM (
        SELECT
        DATE('2023-12-28') as usage_date,
        DATE('2023-12-01') as invoice_month,
        '01C233-D025C4-615139' as billing_account_id,
        '' as projeto_id,
        '' as projeto,
        'Invoice - GCP AJUSTE ERRO' as servico_nome,
        'A656-35D2-EF7F' as servico_id,
        '5AB4-0B3B-9EEC' as sku_id,
        'GCP AJUSTE ERRO'as sku_description,
        5.8869000000509217 as currency_conversion_rate,
        0 as custo,
        0 as creditos,
        0 as credito_cud,
        400541.37 as ajuste,
        0 as custo_suporte,
        0 as credito_suporte,
        CAST(NULL AS STRING) AS labels_string,
        CAST(NULL AS STRING) AS tags_string,
        CAST(NULL AS STRING) AS system_labels_string,
        CAST(NULL AS STRING) AS resource_name,
        CAST(NULL AS STRING) AS resource_global_name,
        CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
        CAST(NULL AS STRING) AS usage_pricing_unit
    )
    WHERE invoice_month = '{{invoice_month}}'

    UNION ALL

    SELECT
      usage_date,
      main.invoice_month,
      main.billing_account_id,
      main.project_id,
      main.project_name AS projeto,
      main.service_description AS servico_nome,
      main.service_id AS servico_id,
      main.sku_id,
      main.sku_description,
      main.currency_conversion_rate,
      CASE
        WHEN (main.service_description IN ('Support', 'Invoice') AND main.sku_id != '4786-4CF8-8CB5') THEN 0
        WHEN (main.sku_description IN ("credito-jv-atendimento", "credito-gemini", "credito-rec-ai")) THEN main.credits_amount
        ELSE cost
      END AS custo,
      CASE
        WHEN (main.service_description IN ('Support', 'Invoice') AND main.sku_id != '4786-4CF8-8CB5') OR (main.credits_type IN ("COMMITTED_USAGE_DISCOUNT", "COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE", "FEE_UTILIZATION_OFFSET")) THEN 0
        WHEN (main.sku_description IN ("credito-jv-atendimento", "credito-gemini", "credito-rec-ai")) THEN main.cost
        ELSE main.credits_amount
      END AS creditos,
      CASE
        -- Exclude non-relevant services
        WHEN (
          main.service_description IN ('Support', 'Invoice')
          AND main.sku_id != '4786-4CF8-8CB5'
        ) THEN 0

        -- Explicit CUD credits (legacy)
        WHEN main.credits_type IN (
          'COMMITTED_USAGE_DISCOUNT',
          'COMMITTED_USAGE_DISCOUNT_DOLLAR_BASE',
          'FEE_UTILIZATION_OFFSET'
        ) THEN main.credits_amount

        -- Price-based CUD (new billing model)
        WHEN main.consumption_model_description != 'Default'
        THEN (net_cost - cost)
      ELSE 0
      END AS credito_cud,
      CASE
          -- ignorando ajuste para dezembro de 2023 devido a um erro de cobranca da GCP que nao sera corrigido por eles
          -- sao R$334,869.78 de ajuste mais uma fatura extra de R$400,541.37 que estamos pagando a mais em dezembro
          -- totalizando R$735,411.15 que deverao ser devolvidos como ajuste futuro
          WHEN main.invoice_month = '2023-12-01' THEN 0 --400541.37
          WHEN main.service_description = 'Invoice' THEN COALESCE(cost, net_cost) ELSE 0
      END ajuste,
      -- Distribuição
      (SAFE_DIVIDE(CASE WHEN (map_service.suporte IS NULL AND main.service_description IN ('Support', 'Invoice')) OR (map_service.suporte IS FALSE) THEN 0 ELSE main.cost END, tot.total_mes_sem_suporte)) * tot.total_mes_suporte AS custo_suporte,
      (SAFE_DIVIDE(CASE WHEN (map_service.suporte IS NULL AND main.service_description IN ('Support', 'Invoice')) OR (map_service.suporte IS FALSE) THEN 0 ELSE main.cost END, tot.total_mes_sem_suporte)) * tot.total_mes_credito_suporte AS credito_suporte,
      labels_string,
      tags_string,
      system_labels_string,
      resource_name,
      resource_global_name,
      usage_amount_in_pricing_units,
      usage_pricing_unit
    FROM silver main
    LEFT JOIN `{{gcp_marketplace_services_table}}` map_service on map_service.service_id = main.service_id
    LEFT JOIN (
    SELECT
        invoice_month,
        billing_account_id,
        SUM(CASE WHEN (bill.service_description = 'Support') THEN cost ELSE 0 END) total_mes_suporte,
        SUM(CASE WHEN (map_service.suporte IS NULL AND (bill.service_description IN ('Support', 'Invoice') )) OR (map_service.suporte IS FALSE) THEN 0 ELSE cost END ) total_mes_sem_suporte,
        SUM(CASE WHEN (bill.service_description = 'Support') THEN credits_amount ELSE 0 END) AS total_mes_credito_suporte,
        SUM(CASE WHEN bill.service_description = 'Invoice' THEN cost ELSE 0 END) total_mes_ajuste
    FROM
        silver bill
    LEFT JOIN `{{gcp_marketplace_services_table}}` map_service on map_service.service_id = bill.service_id
    WHERE bill.sku_id != '4786-4CF8-8CB5'
    GROUP BY
        invoice_month,
        billing_account_id) tot
    ON main.invoice_month = tot.invoice_month AND main.billing_account_id = tot.billing_account_id
),
pre_cc_business_data AS (
SELECT
  main.billing_account_id as billing_account_id,
  main.usage_date as usage_date,
  main.invoice_month as invoice_month,
  CASE
    WHEN main.sku_id = '4786-4CF8-8CB5' THEN 'GL180606001'
    ELSE COALESCE(omni.cc, map_service.cc, map_sku.cc, '-')
  END AS cc,
  IFNULL(replace(lower(COALESCE(omni.workstream, map_service.workstream, map_sku.workstream)), " ","-"), 'workstream-nao-identificado') AS workstream,
  CASE
    WHEN main.sku_id = '4786-4CF8-8CB5' THEN 'missao-critica'
    WHEN IFNULL(replace(lower(COALESCE(omni.iniciativa, map_service.iniciativa, map_sku.iniciativa)), " ","-"), 'iniciativa-nao-identificada') = 'looker' THEN 'looker-mktplace'
    ELSE IFNULL(replace(lower(COALESCE(omni.iniciativa, map_service.iniciativa, map_sku.iniciativa)), " ","-"), 'iniciativa-nao-identificada')
  END  AS iniciativa,
  main.projeto_id as projeto_id,
  main.projeto as projeto,
  main.servico_nome as servico_nome,
  main.servico_id,
  main.sku_description,
  main.currency_conversion_rate,
  main.sku_id,
  labels_string,
  tags_string,
  system_labels_string,
  resource_name,
  resource_global_name,
  SUM(main.custo) AS custo,
  SUM(main.creditos) AS creditos,
  IFNULL(SUM(main.credito_cud), 0) AS credito_cud,
  SUM(main.ajuste) AS ajuste,
  SUM(main.custo_suporte) AS custo_suporte,
  SUM(main.credito_suporte) AS credito_suporte,
  SUM(usage_amount_in_pricing_units) AS usage_amount_in_pricing_units,
  usage_pricing_unit
FROM gold_pre_foundation main
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.tb_gcp_marketplace_services` map_service
  ON map_service.service_id = main.servico_id
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.tb_gcp_marketplace_services` map_sku
  ON map_sku.sku_id = main.sku_id
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.omnicloud_contas_raw` omni ON projeto_id = omni.id
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.gcp_foundation_raw` found ON projeto_id = found.projeto
WHERE (
    (main.servico_nome <> 'Support' OR main.sku_id = '4786-4CF8-8CB5')
)
GROUP BY ALL
)
SELECT
  base.*,
  COALESCE(cc.n1, 'DADOS INDISPONÍVEIS') AS diretoria_n1,
  COALESCE(cc.n2, 'DADOS INDISPONÍVEIS') AS diretoria_n2,
  COALESCE(cc.n3, 'DADOS INDISPONÍVEIS') AS gerencia_n3,
  COALESCE(cc.responsavel_n4, 'DADOS INDISPONÍVEIS') AS gestor,
  COALESCE(cc.n4, 'DADOS INDISPONÍVEIS') AS area_n4,
  COALESCE(cc.nome, 'DADOS INDISPONÍVEIS') AS cc_nome,
  COALESCE(base.cc, cc.codigo, 'DADOS INDISPONÍVEIS') AS cc_codigo,
FROM pre_cc_business_data base
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.centro_de_custo_raw` cc ON CAST(cc.codigo AS STRING) = base.cc
"""

DELETE_GOLD_PRE_FOUNDATION_DATA = """
DELETE FROM `{{gcp_label_gold_pre_foundation_table}}`
WHERE invoice_month = '{{invoice_month}}'
"""

INSERT_GOLD_PRE_FOUNDATION_DATA = """
INSERT INTO `{{final_table}}`
(
  billing_account_id, usage_date, invoice_month,
  workstream, iniciativa, diretoria_n1, diretoria_n2,
  gerencia_n3, gestor, area_n4,
  cc_nome, cc_codigo, projeto_id, projeto,
  servico_nome, servico_id, sku_id, sku_description,
  currency_conversion_rate, custo, creditos, credito_cud, ajuste,
  custo_suporte, credito_suporte, resource_name,
  resource_global_name, labels, tags, system_labels,
  usage_amount_in_pricing_units, usage_pricing_unit
)
WITH gold AS (
  {{select_gold_pre_foundation_data}}
)
SELECT
  billing_account_id,
  usage_date,
  invoice_month,
  workstream,
  iniciativa,
  diretoria_n1,
  diretoria_n2,
  gerencia_n3,
  gestor,
  area_n4,
  cc_nome,
  cc_codigo,
  projeto_id,
  projeto,
  servico_nome,
  servico_id,
  sku_id,
  sku_description,
  currency_conversion_rate,
  custo,
  creditos,
  credito_cud,
  ajuste,
  custo_suporte,
  credito_suporte,
  resource_name,
  resource_global_name,
  ( SELECT ARRAY_AGG(STRUCT(
      JSON_VALUE(unnested_labels, '$.key') AS key,
      JSON_VALUE(unnested_labels, '$.value') AS value))
    FROM UNNEST(JSON_EXTRACT_ARRAY(labels_string, "$")) AS unnested_labels
  ) AS labels,
  ( SELECT ARRAY_AGG(STRUCT(
      JSON_VALUE(unnested_tags, '$.key') AS key,
      JSON_VALUE(unnested_tags, '$.value') AS value,
      CAST(JSON_VALUE(unnested_tags, '$.inherited') AS BOOL) AS inherited,
      JSON_VALUE(unnested_tags, '$.namespace') AS namespace))
    FROM UNNEST(JSON_EXTRACT_ARRAY(tags_string, "$")) AS unnested_tags
  ) AS tags,
  ( SELECT ARRAY_AGG(STRUCT(
      JSON_VALUE(unnested_system_labels, '$.key') AS key,
      JSON_VALUE(unnested_system_labels, '$.value') AS value))
    FROM UNNEST(JSON_EXTRACT_ARRAY(system_labels_string, "$")) AS unnested_system_labels
  ) AS system_labels,
  usage_amount_in_pricing_units,
  usage_pricing_unit
FROM gold
"""

CHECK_GOLD_PRE_FOUNDATION_DATA = """
WITH
gold AS (
  {{select_gold_pre_foundation_data}}
)
SELECT
  CASE
    -- remove ajuste e reaplica os valores de ajuste da silver mais a fatura que veio a mais em dezembro
    WHEN invoice_month = '2023-12-01' THEN SUM(custo + custo_suporte) + (400541.37 - 699496.39 - 35914.76) + (-28330.58)
    ELSE SUM(custo + custo_suporte + ajuste)
  END AS custo_gold,
  SUM(creditos + credito_cud + credito_suporte) AS creditos_gold,
  (SELECT
    SUM(
      CASE
        WHEN service_description = 'Invoice' THEN COALESCE(cost, net_cost)
        ELSE IFNULL(cost, 0)
      END
    )
   FROM
    `{{gcp_billing_silver}}`
   WHERE invoice_month = '{{invoice_month}}') AS custo_silver,
  (SELECT
    SUM(
      IFNULL(credits_amount, 0)
      + CASE
          WHEN service_description IN ('Support', 'Invoice') THEN 0
          ELSE IFNULL(net_cost, 0) - IFNULL(cost, 0)
        END
    )
   FROM
    `{{gcp_billing_silver}}`
   WHERE invoice_month = '{{invoice_month}}') AS creditos_silver,
FROM gold
GROUP BY invoice_month
"""
