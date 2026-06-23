"""SQL da camada Gold, migrado literalmente de `gcp_labels/templates/gold_query.py`
(legado). Fonte de verdade do negócio — não simplificar, corrigir ou "limpar"
nada aqui nesta entrega. Qualquer correção de comportamento é decisão
pós-reconciliação (`qa-reconciliation`), não desta migração.

Observações confirmadas por leitura do legado:

1. `SELECT_GOLD_DATA` lê de `tb_gcp_gold_pre_foundation` (não da Silver
   diretamente) e aplica o rateio Foundation: calcula `custo_foundation`/
   `credito_foundation`/`cud_foundation` ratejando o total Foundation
   (`tb_gcp_billing_foundation_labels_dashboard`) proporcionalmente ao custo
   "sem foundation" de cada linha elegível (billing accounts Infra-Digital/POCs,
   excluindo serviços de marketplace).
2. Contém períodos de exclusão de rateio Komodo/SRE (a partir de 2025-06) e
   SMTP/Infra (a partir de 2025-08) — mesmo padrão temporal de
   `templates/gold_foundation_query.py`. Mantido literal, incluindo o
   comentário-lembrete no SQL para ajustar a cláusula quando um novo rateio
   entrar.
3. `CHECK_GOLD_DATA` tem o mesmo hardcode de correção financeira para
   `invoice_month = '2023-12-01'` presente em `gold_pre_foundation_query.py`
   (erro histórico de cobrança da GCP). Replicado literalmente.
4. Diversas referências a `gglobo-billing-hdg-prd.billing_raw.*` (marketplace
   services, `gcp_foundation_raw`) são hardcoded mesmo quando a camada roda em
   homologação — fora de escopo desta migração, apenas referenciadas via SQL.
"""

from __future__ import annotations

SELECT_GOLD_DATA = """
WITH
rateios_gold AS (
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
    labels,
    tags,
    system_labels,
    usage_amount_in_pricing_units,
    usage_pricing_unit
  FROM `{{project_id}}.billing_gold.tb_gcp_gold_pre_foundation`
  WHERE
        -- Antes de Junho: permanece tudo igual, antes de qualquer rateio feito
      invoice_month < '2025-06-01'
    OR
    -- A partir de Junho, retira-se o Rateio do Komodo/SRE (mas só até julho, pois agosto já vem outro rateio)
    (
      invoice_month >= '2025-06-01' AND invoice_month < '2025-08-01'
      AND projeto_id NOT IN ('gglobo-sre-hdg-hub', "gglobo-k6-qa-hdg-prd")
    )
    OR
    -- A partir de Agosto, entra o rateio do SMTP/Infra, além do Komodo que já existia
    (
      invoice_month >= '2025-08-01'
      AND projeto_id NOT IN ('gglobo-sre-hdg-hub', 'gglobo-infraessentials-hub', "gglobo-k6-qa-hdg-prd")
    )
    OR projeto_id IS NULL
    -- Sempre que entrar um novo rateio, lembrar de ajustar o período da clásula anterior


  UNION ALL

    SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    workstream,
    iniciativa,
    diretoria_n1,
    diretoria AS diretoria_n2,
    gerencia_lider AS gerencia_n3,
    gestor,
    area AS area_n4,
    cc_nome,
    cc_codigo,
    projeto_id,
    projeto_id AS projeto,
    servico_nome,
    CAST(NULL AS STRING) AS servico_id,
    CAST(NULL AS STRING) AS sku_id,
    sku_description,
    0. AS currency_conversion_rate,
    custo,
    creditos,
    credito_cud,
    ajuste,
    custo_suporte,
    credito_suporte,
    NULL AS resource_name,
    NULL AS resource_global_name,
    NULL AS labels,
    NULL AS tags,
    NULL AS system_labels,
    CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
    CAST(NULL AS STRING) AS usage_pricing_unit
  FROM `{{project_id}}.billing_gold.vw_gcp_komodo_labels`
  WHERE
    invoice_month >= '2025-06-01'
    AND (projeto_id = 'gglobo-k6-qa-hdg-prd' OR (projeto_id = 'gglobo-sre-hdg-hub' AND cc_codigo NOT IN ("GL181403002")))

    UNION ALL

    SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    workstream,
    iniciativa,
    diretoria_n1,
    diretoria AS diretoria_n2,
    gerencia_lider AS gerencia_n3,
    gestor,
    area AS area_n4,
    cc_nome,
    cc_codigo,
    projeto_id,
    projeto_id AS projeto,
    servico_nome,
    CAST(NULL AS STRING) AS servico_id,
    CAST(NULL AS STRING) AS sku_id,
    sku_description,
    0. AS currency_conversion_rate,
    custo,
    creditos,
    credito_cud,
    ajuste,
    custo_suporte,
    credito_suporte,
    NULL AS resource_name,
    NULL AS resource_global_name,
    NULL AS labels,
    NULL AS tags,
    NULL AS system_labels,
    CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
    CAST(NULL AS STRING) AS usage_pricing_unit
  FROM `{{project_id}}.billing_gold.vw_gcp_smtp_labels`
  WHERE
    invoice_month >= "2025-08-01" -- Rateio apenas a partir de Agosto 2025
    AND projeto_id = "gglobo-infraessentials-hub"
    AND cc_codigo NOT IN ("GL181402003") -- Remove apenas o CC do César (mantendo os demais, que foram para a aba unificada como foundation)

),

total_foundation AS (
  SELECT
    invoice_month,
    SUM(custo + custo_suporte + ajuste) AS total_mes_foundation,
    SUM(creditos + credito_suporte) AS total_mes_credito_foundation,
    SUM(credito_cud) AS total_mes_cud_foundation
  FROM `{{gcp_billing_foundation_labels_dashboard}}`
  WHERE invoice_month ='{{invoice_month}}'
  GROUP BY ALL
),

total_mes_sem_foundation AS (
SELECT
    tb.invoice_month,
    SUM(
      CASE
        WHEN
          -- non-foundation rows (not listed in foundation)
          inner_found.projeto IS NULL
          -- OR sre-hdg-hub project when not foundation
         OR (projeto_id IN ("gglobo-sre-hdg-hub") AND invoice_month >= '2025-06-01')
         OR (projeto_id IN ("gglobo-infraessentials-hub") AND invoice_month >= '2025-08-01')
        THEN
          CASE WHEN tb.servico_nome != "Strata"
               AND billing_account_id IN ('01C233-D025C4-615139', '01475D-50D30C-FE7981')
          THEN custo + custo_suporte + ajuste
          ELSE 0 END
        ELSE 0
      END
    ) AS total_mes_sem_foundation,

    SUM(
      CASE
        WHEN inner_found.projeto IS NULL
         OR (projeto_id IN ("gglobo-sre-hdg-hub") AND invoice_month >= '2025-06-01')
         OR (projeto_id IN ("gglobo-infraessentials-hub") AND invoice_month >= '2025-08-01')
        THEN
          CASE WHEN tb.servico_nome != "Strata"
               AND billing_account_id IN ('01C233-D025C4-615139', '01475D-50D30C-FE7981')
          THEN creditos + credito_suporte
          ELSE 0 END
        ELSE 0
      END
    ) AS total_mes_credito_sem_foundation,

    SUM(
      CASE
        WHEN inner_found.projeto IS NULL
         OR (projeto_id IN ("gglobo-sre-hdg-hub") AND invoice_month >= '2025-06-01')
         OR (projeto_id IN ("gglobo-infraessentials-hub") AND invoice_month >= '2025-08-01')
        THEN
          CASE WHEN tb.servico_nome != "Strata"
               AND billing_account_id IN ('01C233-D025C4-615139', '01475D-50D30C-FE7981')
          THEN credito_cud
          ELSE 0 END
        ELSE 0
      END
    ) AS total_mes_cud_sem_foundation,
  FROM rateios_gold tb
  LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.sheets_gcp_projetos_servicos_foundation` inner_found ON tb.projeto_id = inner_found.projeto OR tb.servico_nome = inner_found.servico
  LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.tb_gcp_marketplace_services` s on s.service_id = tb.servico_id
  WHERE s.service_id IS NULL AND billing_account_id != "014B76-D5E812-92EC3C" and tb.invoice_month = '{{invoice_month}}'
  GROUP BY invoice_month
),

base_rateio_foundation AS (
SELECT
  a.invoice_month,
  total_mes_foundation,
  total_mes_credito_foundation,
  total_mes_cud_foundation,
  total_mes_sem_foundation,
  total_mes_credito_sem_foundation,
  total_mes_cud_sem_foundation
FROM total_foundation a
LEFT JOIN total_mes_sem_foundation b ON a.invoice_month = b.invoice_month
)

SELECT
  billing_account_id,
  usage_date,
  main.invoice_month,
  main.workstream,
  CASE
    WHEN main.iniciativa = "looker" THEN "looker-mktplace"
    WHEN main.iniciativa = "cdn-internacional" AND main.sku_id IN ("2D9A-A807-BCF7") AND main.invoice_month >= "2026-01-01" THEN "cdn-nacional"
    ELSE main.iniciativa
  END AS iniciativa,
  main.diretoria_n1,
  main.diretoria_n2,
  main.gerencia_n3,
  main.gestor,
  main.area_n4,
  main.cc_nome,
  main.cc_codigo,
  CASE
    WHEN map_service.service_id IS NOT NULL AND main.invoice_month >= "2026-01-01" THEN "marketplace"
    ELSE main.projeto_id
  END AS projeto_id,
  main.projeto,
  main.servico_nome,
  main.servico_id,
  main.sku_id,
  main.sku_description,
  main.currency_conversion_rate,
  main.custo,
  main.creditos,
  main.credito_cud,
  main.ajuste,
  main.custo_suporte,
  main.credito_suporte,
  main.resource_name,
  main.resource_global_name,
  main.labels,
  main.tags,
  main.system_labels,
  SUM(CASE
        WHEN billing_account_id IN (/*Infra-Digital*/ '01C233-D025C4-615139', /*POCs*/ '01475D-50D30C-FE7981') AND map_service.service_id IS NULL
          THEN IFNULL(SAFE_DIVIDE(tot.total_mes_foundation * (custo + custo_suporte + ajuste), tot.total_mes_sem_foundation), 0)
        ELSE 0
      END) AS custo_foundation,
  SUM(CASE
        WHEN billing_account_id IN (/*Infra-Digital*/ '01C233-D025C4-615139', /*POCs*/ '01475D-50D30C-FE7981') AND map_service.service_id IS NULL
          THEN IFNULL(SAFE_DIVIDE(tot.total_mes_credito_foundation * (custo + custo_suporte + ajuste), tot.total_mes_sem_foundation), 0)
        ELSE 0
      END) AS credito_foundation,
  SUM(CASE
        WHEN billing_account_id IN (/*Infra-Digital*/ '01C233-D025C4-615139', /*POCs*/ '01475D-50D30C-FE7981') AND map_service.service_id IS NULL
          THEN IFNULL(SAFE_DIVIDE(tot.total_mes_cud_foundation * (custo + custo_suporte + ajuste), tot.total_mes_sem_foundation), 0)
        ELSE 0
      END) AS cud_foundation,
  usage_amount_in_pricing_units,
  usage_pricing_unit
FROM rateios_gold main
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.tb_gcp_marketplace_services` map_service on map_service.service_id = main.servico_id
LEFT JOIN `gglobo-billing-hdg-prd.billing_raw.gcp_foundation_raw` found ON projeto_id = found.projeto
LEFT JOIN base_rateio_foundation tot ON main.invoice_month = tot.invoice_month
WHERE (
  found.projeto IS NULL
   OR (main.projeto_id IN ("gglobo-sre-hdg-hub") AND main.invoice_month >= '2025-06-01')
   OR (main.projeto_id IN ("gglobo-infraessentials-hub") AND main.invoice_month >= '2025-08-01')
)
AND (
    (main.servico_nome <> 'Support' OR main.sku_id = '4786-4CF8-8CB5')
    AND main.servico_nome <> 'Strata'
)
AND main.invoice_month = '{{invoice_month}}'
GROUP BY ALL
"""

DELETE_GOLD_DATA = """
DELETE FROM `{{gcp_label_gold_table}}`
WHERE invoice_month = '{{invoice_month}}'
"""

INSERT_GOLD_DATA = """
INSERT INTO `{{final_table}}`
(
  billing_account_id, usage_date, invoice_month,
  workstream, iniciativa, diretoria_n1, diretoria_n2,
  gerencia_n3, gestor, area_n4,
  cc_nome, cc_codigo, projeto_id, projeto,
  servico_nome, servico_id, sku_id, sku_description,
  currency_conversion_rate, custo, creditos, credito_cud, ajuste,
  custo_suporte, credito_suporte, custo_foundation,
  credito_foundation, cud_foundation, resource_name,
  resource_global_name, labels, tags, system_labels,
  usage_amount_in_pricing_units, usage_pricing_unit
)
WITH gold AS (
  {{select_gold_data}}
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
  custo_foundation,
  credito_foundation,
  cud_foundation,
  resource_name,
  resource_global_name,
  labels,
  tags,
  system_labels,
  usage_amount_in_pricing_units,
  usage_pricing_unit
FROM gold
"""

CHECK_GOLD_DATA = """
WITH
gold AS (
  {{select_gold_data}}
)
SELECT
  CASE
    -- remove ajuste e reaplica os valores de ajuste da silver mais a fatura que veio a mais em dezembro
    WHEN invoice_month = '2023-12-01' THEN SUM(custo + custo_suporte) + (400541.37 - 699496.39 - 35914.76) + (-28330.58)
    ELSE SUM(custo + custo_suporte + custo_foundation + ajuste)
  END AS custo_gold,
  SUM(creditos + credito_cud + credito_suporte + cud_foundation + credito_foundation) AS creditos_gold,
  (SELECT
    SUM(custo + custo_suporte + ajuste) AS cost,
    FROM
    `{{gold_pre_foundation}}`
    WHERE invoice_month = '{{invoice_month}}') AS custo_silver,
  (SELECT
    SUM(credito_cud + credito_suporte + creditos) AS credits,
    FROM
    `{{gold_pre_foundation}}`
    WHERE invoice_month = '{{invoice_month}}') AS creditos_silver,
FROM gold
GROUP BY invoice_month
"""

BACKUP_PESOS_RATEIO_BQ_FORA_DA_ORG = """
INSERT INTO `gglobo-billing-hdg-prd.billing_gold.backup_rateio_bq_slots_fora_org`
(
  project_id,
  sku_description,
  slots_ratio,
  total_daily_slot_usage_project,
  usage_date
)
SELECT
  t.project_id,
  t.sku_description,
  t.slots_ratio,
  t.total_daily_slot_usage_project,
  t.usage_date
FROM `valiant-circuit-129220.devfinops_bq.tb_rateio_slots_bq_fora_org` t
LEFT JOIN `gglobo-billing-hdg-prd.billing_gold.backup_rateio_bq_slots_fora_org` backup ON backup.project_id = t.project_id AND backup.usage_date = t.usage_date AND backup.slots_ratio = t.slots_ratio
WHERE backup.slots_ratio IS NULL
"""
