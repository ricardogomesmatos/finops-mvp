SELECT_RAW_LABEL_DATA = r"""
WITH original_data_squad AS (
  SELECT
    recurso,
    CASE WHEN squad IS NULL THEN "classificação-não-aplicável" ELSE squad END AS squad,
  FROM
    `gglobo-billing-hdg-prd.billing_gold.tb_gcp_custo_unitario`
  WHERE
    plataforma = "Projeto GCP"
  GROUP BY ALL
),
original_data_produto AS (
  SELECT
    recurso,
    CASE WHEN produto IS NULL THEN "produto-nao-cadastrado" ELSE produto END AS produto,
  FROM
    `gglobo-billing-hdg-prd.billing_gold.tb_gcp_custo_unitario`
  WHERE
    plataforma = "Projeto GCP"
  GROUP BY ALL
),
mapeamento_squad_produto AS (
  SELECT
    COALESCE(s.recurso,p.recurso) as project_id,
    ARRAY<STRUCT<key STRING, value STRING>>[
      STRUCT('squad', squad),
      STRUCT('produto', produto)
    ] AS labels_from_sheets
  FROM
    original_data_squad s JOIN original_data_produto p ON s.recurso=p.recurso
),
gcp_corrections AS (
    SELECT *
    FROM (
        SELECT
        DATE('2023-12-28') as usage_date,
        DATE('2023-12-01') as invoice_month,
        '01C233-D025C4-615139' as billing_account_id,
        '' as project_id, 
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
        [] AS labels,
        [] AS tags,
        [] AS system_labels)
    WHERE invoice_month = '{{invoice_month}}'
),
silver AS (
    SELECT
        raw.* EXCEPT(usage_start_time, usage_amount, cost, net_cost, credits_amount, labels, tags, system_labels, usage_amount_in_pricing_units),
        DATE(raw.usage_start_time) AS usage_date,
        CASE
          # Quando a GCP tem as labels.key produto E squad, mantemos as labels da GCP independente do que tiver na planilha
          WHEN REGEXP_CONTAINS(to_json_string(raw.labels), r'\bproduto\b') AND REGEXP_CONTAINS(to_json_string(raw.labels), r'\bsquad\b')
            THEN TO_JSON_STRING(IFNULL(raw.labels,[]))
          # Quando a GCP tem a label produto mas não tem a label squad, mantemos o produto da GCP e trazemos apenas o squad da planilha
          WHEN REGEXP_CONTAINS(to_json_string(raw.labels), r'\bproduto\b') AND NOT REGEXP_CONTAINS(to_json_string(raw.labels), r'\bsquad\b')
            THEN TO_JSON_STRING(
                ARRAY_CONCAT(
                    [(
                        SELECT STRUCT(l.key, l.value)
                        FROM UNNEST(IFNULL(msp.labels_from_sheets, [])) AS l
                        WHERE l.key = 'squad'
                        LIMIT 1
                    )],
                    IFNULL(raw.labels, [])
                    )
                )
          # Quando a GCP não tem a label produto mas tem a label squad e não temos a classificação de squad na planilha, trazemos apenas a classificação de produto da planilha
          WHEN NOT REGEXP_CONTAINS(to_json_string(raw.labels), r'\bproduto\b') AND REGEXP_CONTAINS(to_json_string(raw.labels), r'\bsquad\b') AND REGEXP_CONTAINS(to_json_string(msp.labels_from_sheets), r'\bclassificação-não-aplicável\b')
            THEN TO_JSON_STRING(
                ARRAY_CONCAT(
                    [(
                        SELECT STRUCT(l.key, l.value)
                        FROM UNNEST(IFNULL(msp.labels_from_sheets, [])) AS l
                        WHERE l.key = 'produto'
                        LIMIT 1
                    )],
                    IFNULL(raw.labels, [])
                    )
                )    
          # Quando a GCP não tem a label produto mas tem a label squad, trazemos apenas o produto
          WHEN NOT REGEXP_CONTAINS(to_json_string(raw.labels), r'\bproduto\b') AND REGEXP_CONTAINS(to_json_string(raw.labels), r'\bsquad\b') AND NOT REGEXP_CONTAINS(to_json_string(msp.labels_from_sheets), r'\bclassificação-não-aplicável\b')
            THEN TO_JSON_STRING(
                ARRAY_CONCAT(
                    IFNULL(msp.labels_from_sheets, []),
                    ARRAY(
                      SELECT STRUCT(l.key, l.value)
                      FROM UNNEST(IFNULL(raw.labels, [])) AS l
                      WHERE l.key != 'squad'
                    )
                  )
                )
        ELSE TO_JSON_STRING(ARRAY_CONCAT(IFNULL(msp.labels_from_sheets,[]), IFNULL(raw.labels,[])))
        END AS labels_string,
        TO_JSON_STRING(raw.tags) AS tags_string,
        TO_JSON_STRING(raw.system_labels) AS system_labels_string,
        SUM(raw.usage_amount) AS usage_amount,
        SUM(raw.cost) AS cost,
        SUM(raw.net_cost) AS net_cost,
        SUM(IFNULL(raw.credits_amount,0)) AS credits_amount,
        SUM(usage_amount_in_pricing_units) as usage_amount_in_pricing_units
    FROM `{{project_id}}.billing_raw.vw_gcp_billing_raw_label` raw
    LEFT JOIN mapeamento_squad_produto msp
        ON msp.project_id = raw.project_id
    WHERE
        DATE(raw.PARTITION_TIME) BETWEEN '{{partition_start}}' AND '{{partition_end}}'
        AND raw.invoice_month = '{{invoice_month}}'
    GROUP BY ALL
)
SELECT *
FROM silver
"""

INSERT_SILVER_DATA = """
INSERT INTO `{{gcp_silver_label_table}}` (
    usage_date, usage_amount, usage_amount_in_pricing_units,
    cost, net_cost, credits_amount, record_type, billing_account_id,
    service_id, service_description, sku_id, sku_description,
    project_id, project_number, project_name, project_ancestry_numbers,
    location_location, location_country, location_region, location_zone,
    currency, currency_conversion_rate, usage_unit, usage_pricing_unit,
    credits_name, credits_full_name, credits_id, credits_type, invoice_month,
    cost_type, adjustment_info_id, adjustment_info_description,
    adjustment_info_mode, adjustment_info_type, labels_string, tags_string, system_labels_string,
    resource_name, resource_global_name, consumption_model_description, price_effective_price_default,
    price_effective_price, price_pricing_unit_quantity
)
WITH silver AS ({{select_silver_data}})
SELECT
    usage_date,
    usage_amount,
    usage_amount_in_pricing_units,
    cost,
    net_cost,
    credits_amount,
    record_type,
    billing_account_id,
    service_id,
    service_description,
    sku_id,
    sku_description,
    project_id,
    project_number,
    project_name,
    project_ancestry_numbers,
    location_location,
    location_country,
    location_region,
    location_zone,
    currency,
    currency_conversion_rate,
    usage_unit,
    usage_pricing_unit,
    credits_name,
    credits_full_name,
    credits_id,
    credits_type,
    invoice_month,
    cost_type,
    adjustment_info_id,
    adjustment_info_description,
    adjustment_info_mode,
    adjustment_info_type,
    labels_string,
    tags_string,
    system_labels_string,
    resource_name,
    resource_global_name,
    consumption_model_description,
    price_effective_price_default,
    price_effective_price,
    price_pricing_unit_quantity
FROM silver
"""

CHECK_SILVER_DATA = """
WITH silver AS ({{select_silver_data}})
SELECT
    SUM(main.custo_raw) AS custo_raw,
    SUM(main.credito_raw) AS credito_raw,
    SUM(main.custo_silver) AS custo_silver,
    SUM(main.credito_silver) AS credito_silver
FROM (
    SELECT
        0.0 AS custo_raw,
        0.0 AS credito_raw,
        SUM(silver.cost) AS custo_silver,
        SUM(silver.credits_amount) AS credito_silver,
    FROM silver
    UNION ALL
    SELECT
        SUM(cost),
        SUM(credits_amount),
        0.0,
        0.0
    FROM `{{project_id}}.billing_raw.vw_gcp_billing_raw_label` raw
    WHERE DATE(raw.PARTITION_TIME) BETWEEN '{{partition_start}}' AND '{{partition_end}}'
        AND raw.invoice_month = '{{invoice_month}}'
) main
"""

DELETE_SILVER_DATA = """
DELETE FROM `{{gcp_silver_label_table}}`
WHERE invoice_month = '{{invoice_month}}'
"""