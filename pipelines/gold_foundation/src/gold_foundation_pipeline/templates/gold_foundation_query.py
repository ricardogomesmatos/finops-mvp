"""SQL da camada Gold Foundation, migrado literalmente de
`gcp_labels/templates/gold_foundation_query.py` (legado).

Fonte de verdade do negócio — não simplificar, corrigir ou "limpar" nada aqui
nesta entrega. Qualquer correção de comportamento é decisão pós-reconciliação
(`qa-reconciliation`), não desta migração.

Observações confirmadas por leitura do legado:

1. Esta camada lê de `tb_gcp_gold_pre_foundation` (camada anterior do
   medalhão) e faz `INNER JOIN` com uma planilha de projetos/serviços
   Foundation (`sheets_gcp_projetos_servicos_foundation`), com o projeto de
   origem hardcoded (`gglobo-billing-hdg-prd`) mesmo quando esta camada roda
   em homologação — replicado literalmente, não parametrizado.
2. `INSERT_GOLD_FOUNDATION_DASHBOARD_DATA` lê de
   `{{project_id}}.billing_gold.tb_gcp_billing_foundation_labels` com o nome
   da tabela hardcoded no FROM, em vez de reutilizar o parâmetro
   `gcp_gold_label_foundation_table` usado no INSERT acima. Ou seja, se o
   nome da tabela de destino mudasse via env var, esta leitura ficaria
   dessincronizada. Replicado fielmente — não corrigido nesta migração.
3. Contém regras de negócio datadas (períodos de rateio Komodo/SRE a partir
   de 2025-06 e SMTP/Infra a partir de 2025-08) com comentário explícito no
   próprio SQL para lembrar de ajustar a cláusula quando um novo rateio
   entrar. Mantido literal.
"""

from __future__ import annotations

INSERT_GOLD_FOUNDATION_DATA = """
INSERT INTO {{gcp_gold_label_foundation_table}}
(
billing_account_id,
usage_date,
invoice_month,
cc_codigo,
workstream,
iniciativa,
diretoria_n1,
diretoria_n2,
gerencia_n3,
gestor,
area_n4,
cc_nome,
projeto_id,
servico_nome,
sku_description,
custo,
creditos,
ajuste,
custo_suporte,
credito_suporte,
credito_cud,
ambiente,
labels,
tags,
system_labels,
resource_name,
resource_global_name,
usage_amount_in_pricing_units,
usage_pricing_unit
)
SELECT
  billing_account_id,
  usage_date,
  invoice_month,
  cc_codigo,
  workstream,
  main.iniciativa,
  diretoria_n1,
  diretoria_n2,
  gerencia_n3,
  gestor,
  area_n4,
  cc_nome,
  projeto_id,
  servico_nome,
  sku_description,
  custo,
  creditos,
  ajuste,
  custo_suporte,
  credito_suporte,
  credito_cud,
  CASE
    WHEN sku_id = '4786-4CF8-8CB5' THEN 'produção (prd)'
    WHEN LOWER(projeto_id) = 'premiere-270617' THEN 'produção (prd)'
    WHEN LOWER(projeto_id) LIKE '%-prd' THEN 'produção (prd)'
    WHEN LOWER(projeto_id) LIKE '%-prod' THEN 'produção (prd)'
    WHEN LOWER(projeto_id) LIKE '%qa%' THEN 'quality assurance (qa)'
    WHEN LOWER(projeto_id) LIKE '%-dev' THEN 'desenvolvimento (dev)'
    WHEN LOWER(projeto_id) LIKE 'poc-%' or LOWER(projeto_id) LIKE '%-poc' THEN 'proof of concept (poc)'
    WHEN (LOWER(projeto_id) like 'pr%' or projeto_id IS NULL) and servico_nome not in ('Invoice', 'Compute Engine') THEN 'marketplace (mkt)'
    ELSE "produção (prd)"
  END AS ambiente,
  labels,
  tags,
  system_labels,
  resource_name,
  resource_global_name,
  usage_amount_in_pricing_units,
  usage_pricing_unit
FROM `{{gold_pre_foundation_table}}` main
INNER JOIN `gglobo-billing-hdg-prd.billing_raw.sheets_gcp_projetos_servicos_foundation` found ON main.projeto_id = found.projeto OR main.servico_nome = found.servico
WHERE servico_nome NOT IN ("Support")
AND invoice_month = "{{invoice_month}}"
GROUP BY ALL
"""

DELETE_GOLD_FOUNDATION_DATA = """DELETE FROM `{{target_table}}`
WHERE invoice_month = '{{invoice_month}}'"""

INSERT_GOLD_FOUNDATION_DASHBOARD_DATA = """
INSERT INTO {{gcp_gold_label_foundation_dashboard_table}}
(
billing_account_id,
usage_date,
invoice_month,
cc_codigo,
workstream,
iniciativa,
diretoria_n1,
diretoria_n2,
gerencia_n3,
gestor,
area_n4,
cc_nome,
projeto_id,
projeto,
servico_nome,
sku_description,
custo,
creditos,
ajuste,
custo_suporte,
credito_suporte,
credito_cud,
ambiente,
labels,
tags,
system_labels,
resource_name,
resource_global_name,
usage_amount_in_pricing_units,
usage_pricing_unit
)
WITH
cte_final AS (
  SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    cc_codigo,
    workstream,
    iniciativa,
    diretoria_n1,
    diretoria_n2,
    gerencia_n3,
    gestor,
    area_n4,
    cc_nome,
    projeto_id,
    projeto_id AS projeto,
    servico_nome,
    sku_description,
    SUM(custo) AS custo,
    SUM(creditos) AS creditos,
    SUM(ajuste) AS ajuste,
    SUM(custo_suporte) AS custo_suporte,
    SUM(credito_suporte) AS credito_suporte,
    SUM(credito_cud) AS credito_cud,
    ambiente,
    labels,
    tags,
    system_labels,
    resource_name,
    resource_global_name,
    usage_amount_in_pricing_units,
    usage_pricing_unit
  FROM `{{project_id}}.billing_gold.tb_gcp_billing_foundation_labels`
  WHERE
    -- Antes de Junho: permanece tudo igual, antes de qualquer rateio feito
      invoice_month < '2025-06-01'
    OR
    -- A partir de Junho, retira-se o Rateio do Komodo/SRE (mas só até julho, pois agosto já vem outro rateio)
    (
      invoice_month >= '2025-06-01' AND invoice_month < '2025-08-01'
      AND projeto_id NOT IN ('gglobo-sre-hdg-hub')
    )
    OR
    -- A partir de Agosto, entra o rateio do SMTP/Infra, além do Komodo que já existia
    (
      invoice_month >= '2025-08-01'
      AND projeto_id NOT IN ('gglobo-sre-hdg-hub', 'gglobo-infraessentials-hub')
    )
    -- Sempre que entrar um novo rateio, lembrar de ajustar o período da clásula anterior
    OR projeto_id IS NULL
  GROUP BY ALL

  UNION ALL

  SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    cc_codigo,
    workstream,
    iniciativa,
    diretoria_n1,
    diretoria AS diretoria_n2,
    gerencia_lider AS gerencia_n3,
    gestor,
    area AS area_n4,
    cc_nome,
    projeto_id,
    projeto_id AS projeto,
    servico_nome,
    sku_description,
    SUM(custo) AS custo,
    SUM(creditos) AS creditos,
    SUM(ajuste) AS ajuste,
    SUM(custo_suporte) AS custo_suporte,
    SUM(credito_suporte) AS credito_suporte,
    SUM(credito_cud) AS credito_cud,
    ambiente,
    null AS labels,
    null AS tags,
    null AS system_labels,
    null AS resource_name,
    null AS resource_global_name,
    CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
    CAST(NULL AS STRING) AS usage_pricing_unit
  FROM `{{project_id}}.billing_gold.vw_gcp_komodo_labels`
  WHERE
    invoice_month >= "2025-06-01" -- Rateio apenas a partir de Junho 2025
    AND projeto_id = "gglobo-sre-hdg-hub"
    AND cc_codigo IN ("GL181403002") -- Mantendo apenas o CC do Braulio (removendo os demais, que foram para a aba unificada como custo)
  GROUP BY ALL

  UNION ALL

    SELECT
    billing_account_id,
    usage_date,
    invoice_month,
    cc_codigo AS cc,
    workstream,
    iniciativa,
    diretoria_n1,
    diretoria AS diretoria_n2,
    gerencia_lider AS gerencia_n3,
    gestor,
    area AS area_n4,
    cc_nome,
    projeto_id,
    projeto_id AS projeto,
    servico_nome,
    sku_description,
    SUM(custo) AS custo,
    SUM(creditos) AS creditos,
    SUM(ajuste) AS ajuste,
    SUM(custo_suporte) AS custo_suporte,
    SUM(credito_suporte) AS credito_suporte,
    SUM(credito_cud) AS credito_cud,
    ambiente,
    null AS labels,
    null AS tags,
    null AS system_labels,
    null AS resource_name,
    null AS resource_global_name,
    CAST(NULL AS FLOAT64) AS usage_amount_in_pricing_units,
    CAST(NULL AS STRING) AS usage_pricing_unit
  FROM `{{project_id}}.billing_gold.vw_gcp_smtp_labels`
  WHERE
    invoice_month >= "2025-08-01" -- Rateio apenas a partir de Agosto 2025
    AND projeto_id = "gglobo-infraessentials-hub"
    AND cc_codigo IN ("GL181402003") -- Mantendo apenas o CC do César (removendo os demais, que foram para a aba unificada como custo)
  GROUP BY ALL
)

SELECT * FROM cte_final
WHERE invoice_month = '{{invoice_month}}'
"""
