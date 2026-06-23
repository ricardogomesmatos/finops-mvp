"""SQL da camada Unificado, migrado literalmente de
`gcp_labels/templates/gold_unificada_query.py` (legado). Fonte de verdade do
negócio — não simplificar, corrigir ou "limpar" nada aqui nesta entrega.
Qualquer correção de comportamento é decisão pós-reconciliação
(`qa-reconciliation`), não desta migração.

Observações confirmadas por leitura do legado:

1. `SELECT_GOLD_UNIFICADO_DATA` lê de `billing_gold.vw_gcp_unificada_labels`
   (view multicloud não migrada nesta entrega — provavelmente já consolida
   GCP/Tsuru/DBaaS) e enriquece com mapeamentos de produto/squad/app de
   negócio vindos de tabelas externas (`tb_plataformas_de_video_produto_squad`,
   `tb_globoplay_produto_squad`).
2. `CHECK_GOLD_UNIFICADO_DATA` compara o resultado consolidado contra 4 fontes
   "gold" por provedor (GCP, Tsuru, DBaaS e o próprio agregado) — ver
   `check_result_query` no service para o detalhe da lógica de diff.
3. Todas as tabelas/views referenciadas são hardcoded para o projeto de
   produção (`gglobo-billing-hdg-prd`), independentemente do `project_id`
   configurado — fora de escopo desta migração.
"""

from __future__ import annotations

INSERT_GOLD_UNIFICADO_DATA = """
INSERT INTO `{{gcp_gold_unificado_label_table}}`
(
  provedor,
  billing_account_id,
  invoice_month,
  usage_date,
  team_name,
  recurso,
  servico_nome,
  cc_codigo,
  cc_nome,
  workstream,
  iniciativa,
  diretoria_n1,
  diretoria_n2,
  gerencia_n3,
  area_n4,
  gestor,
  labels,
  squad,
  produto,
  custo,
  custo_foundation,
  custo_suporte,
  creditos,
  credito_cud,
  credito_suporte,
  credito_foundation,
  cud_foundation,
  ajuste,
  ambiente,
  project_id,
  sku_description,
  app_negocio,
  resource_name,
  usage_amount_in_pricing_units,
  usage_pricing_unit
)
{{select_gold_unificado_query}}
"""

DELETE_GOLD_UNIFICADO_DATA = """
DELETE FROM `{{gcp_gold_unificado_label_table}}`
WHERE invoice_month = '{{invoice_month}}'
"""

SELECT_GOLD_UNIFICADO_DATA = """
WITH plataformas_de_video_projetos AS (
  SELECT DISTINCT
    plataforma,
    projeto_app_db,
    app_negocio
  FROM `gglobo-billing-hdg-prd.external_tables.tb_plataformas_de_video_produto_squad`
  WHERE plataforma = 'Projeto GCP' AND projeto_app_db IS NOT NULL AND app_negocio IS NOT NULL
),
plataformas_de_video_app_db AS (
  SELECT DISTINCT
    plataforma,
    projeto_app_db,
    time,
    app_negocio
  FROM `gglobo-billing-hdg-prd.external_tables.tb_plataformas_de_video_produto_squad`
  WHERE plataforma != 'Projeto GCP' AND projeto_app_db IS NOT NULL AND app_negocio IS NOT NULL
),
globoplay_projetos AS (
  SELECT DISTINCT
  projeto_or_team_name AS project_id,
  produto,
  squad
FROM
  `gglobo-billing-hdg-prd.external_tables.tb_globoplay_produto_squad`
WHERE
  plataforma = "Projeto GCP"
  AND (produto IS NOT NULL
    OR squad IS NOT NULL)
),
globoplay_app_db AS (
  SELECT
  DISTINCT projeto_or_team_name As team_name,
  app_or_database,
  produto,
  squad
FROM
  `gglobo-billing-hdg-prd.external_tables.tb_globoplay_produto_squad`
WHERE
  plataforma != "Projeto GCP"
  AND (produto IS NOT NULL
    OR squad IS NOT NULL)
)
SELECT
  provedor,
  billing_account_id,
  invoice_month,
  usage_date,
  main.team_name,
  recurso,
  servico_nome,
  main.cc_codigo,
  cc_nome,
  main.workstream,
  main.iniciativa,
  diretoria_n1,
  diretoria,
  gerencia_lider,
  area,
  main.gestor,
  labels,
  COALESCE(globoplay_projetos.squad, globoplay_app_db.squad, main.squad) AS squad,
  COALESCE(globoplay_projetos.produto, globoplay_app_db.produto, main.produto) AS produto,
  custo,
  custo_foundation,
  custo_suporte,
  creditos,
  credito_cud,
  credito_suporte,
  credito_foundation,
  cud_foundation,
  ajuste,
  ambiente,
  main.project_id,
  sku_description,
  CASE
    WHEN servico_nome = "Amagi CLOUDPORT" THEN 'amagi-fast'
    WHEN servico_nome = "Harmonic VOS Solution" THEN 'low-latency'
    ELSE COALESCE(plat_vid_projetos.app_negocio, plat_vid_app_db.app_negocio, 'aplicação-não-identificada')
  END AS app_negocio,
  resource_name,
  usage_amount_in_pricing_units,
  usage_pricing_unit
FROM `{{project_id}}.billing_gold.vw_gcp_unificada_labels` main
LEFT JOIN plataformas_de_video_projetos plat_vid_projetos
ON plat_vid_projetos.projeto_app_db = main.recurso
LEFT JOIN plataformas_de_video_app_db plat_vid_app_db
ON plat_vid_app_db.projeto_app_db=main.recurso AND plat_vid_app_db.time=main.team_name
LEFT JOIN globoplay_projetos
ON globoplay_projetos.project_id = main.recurso
LEFT JOIN globoplay_app_db
ON globoplay_app_db.team_name = main.team_name AND globoplay_app_db.app_or_database = main.recurso
WHERE invoice_month =  '{{invoice_month}}'
"""

CHECK_GOLD_UNIFICADO_DATA = """
WITH gold AS (
  {{select_gold_unificado_query}}
)
SELECT
  CASE WHEN provedor = "Komodo" THEN "GCP" ELSE provedor END AS provedor,
  SUM(custo) AS custo,
  SUM(custo_foundation) AS custo_foundation,
  SUM(custo_suporte) AS custo_suporte,
  SUM(creditos) AS creditos,
  SUM(credito_cud) AS credito_cud,
  SUM(credito_suporte) AS credito_suporte,
  SUM(credito_foundation) AS credito_foundation,
  SUM(cud_foundation) AS cud_foundation,
  SUM(ajuste) AS ajuste
FROM gold
WHERE invoice_month = '{{invoice_month}}'
GROUP BY 1

UNION ALL

SELECT
  "Tsuru_gold" AS provedor,
  SUM(custo) AS custo,
  SUM(custo_foundation) AS custo_foundation,
  SUM(custo_suporte) AS custo_suporte,
  SUM(creditos) AS creditos,
  SUM(credito_cud) AS credito_cud,
  SUM(credito_suporte) AS credito_suporte,
  SUM(credito_foundation) AS credito_foundation,
  SUM(cud_foundation) AS cud_foundation,
  SUM(ajuste) AS ajuste
FROM `{{project_id}}.billing_gold.vw_gcp_tsuru_usage_metering_gold`
WHERE invoice_month = '{{invoice_month}}'

UNION ALL

SELECT
  "Dbaas_gold" AS provedor,
  SUM(custo) AS custo,
  SUM(custo_foundation) AS custo_foundation,
  SUM(custo_suporte) AS custo_suporte,
  SUM(creditos) AS creditos,
  SUM(credito_cud) AS credito_cud,
  SUM(credito_suporte) AS credito_suporte,
  SUM(credito_foundation) AS credito_foundation,
  SUM(cud_foundation) AS cud_foundation,
  0.0 AS ajuste
FROM `{{project_id}}.billing_gold.tb_rateio_dbaas_billing`
WHERE reference_time = '{{invoice_month}}'

UNION ALL

SELECT
  "GCP_gold" AS provedor,
  SUM(custo) AS custo,
  SUM(custo_foundation) AS custo_foundation,
  SUM(custo_suporte) AS custo_suporte,
  SUM(creditos) AS creditos,
  SUM(credito_cud) AS credito_cud,
  SUM(credito_suporte) AS credito_suporte,
  SUM(credito_foundation) AS credito_foundation,
  SUM(cud_foundation) AS cud_foundation,
  SUM(ajuste) AS ajuste
FROM `{{project_id}}.billing_gold.tb_gcp_billing_projeto_ar_label`
WHERE invoice_month = '{{invoice_month}}' AND (projeto_id NOT IN ('gglobo-tsuru-br1-hdg-prd',
    'gglobo-tsuru-br2-hdg-prd',
    'gglobo-tsuru-us1-hdg-prd',
    'gglobo-tsuru-us2-hdg-dev',
    'gglobo-tsuru-dev-qa',
    'gglobo-dbaas-dev-hdg',
    'gglobo-dbaas-prd-hdg',
    'gglobo-dbaas-tsr-dev',
    'gglobo-dbaas-tsr-prd',
    'gglobo-dbaas-hub',
    'gglobo-dbairflow-cpr-prd')
    OR projeto_id IS NULL)
"""
