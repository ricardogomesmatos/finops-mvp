# Reconciliação Gold Pre-Foundation — legado vs. novo (rascunho para dual-run real)

> **Status atual: NÃO EXECUTÁVEL.** Não há ambiente real (dev/prod) do pipeline novo rodando
> ainda — apenas código Python/SQL sem deploy. Este documento existe para a fase de dual-run
> real puxar depois, sem precisar redesenhar a metodologia do zero. Nenhuma query aqui foi
> executada contra BigQuery. Quando houver dual-run, promover estas queries para
> `test_row_count_parity.py` / `test_aggregate_parity.py` / `test_schema_parity.py` executáveis,
> seguindo o padrão descrito em `qa-reconciliation.md`.

## O que será validado

- **Pipeline**: camada Gold Pre-Foundation do medalhão `gcp_labels`.
- **Legado**: `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`, escrita por
  `gcp_labels/services/gold_label_pre_foundation_service.py` (Cloud Function `gcp-cost-with-labels`).
- **Novo**: mesma tabela de destino (`billing_gold.tb_gcp_gold_pre_foundation`), em projeto a
  definir para dual-run (idealmente um projeto de homologação separado, escrevendo em paralelo
  sem sobrescrever o legado — nunca apontar o pipeline novo para a tabela de produção do legado
  antes do cutover aprovado), escrita por `gold_pre_foundation_pipeline.services.gold_pre_foundation_service.GoldPreFoundationService`.
- **Pré-condição não satisfeita ainda**: como o `SELECT` desta camada depende de 5 fontes
  externas fora de escopo desta migração (`vw_gcp_rateio_bq_labels`, `vw_gcp_rateio_bq_labels_v2`,
  `vw_gcp_rateio_armor_fee_label`, `vw_gcp_rateio_databricks_labels`,
  `tb_alocacao_creditos_migration-1-1747074799001`) e da tabela `gcp_billing_silver_label` (que
  precisa já existir populada pela camada Silver, legada ou migrada), o dual-run desta camada só
  é válido se essas 6 fontes forem **idênticas** nos dois ambientes comparados (mesmo projeto/
  dataset, ou cópia fiel). Se o dual-run rodar a Silver migrada à montante, qualquer divergência
  encontrada aqui pode ter origem na Silver, não nesta camada — isolar a causa antes de atribuir
  o bug à Pre-Foundation.
- **Períodos a validar**: no mínimo 2 ciclos de fechamento mensal completos e consecutivos
  (critério de sign-off de cutover), mais o mês `2023-12-01` isoladamente — é o único período com
  hardcode financeiro (`+400541.37` em `gold_pre_foundation`, ajuste assimétrico em
  `CHECK_GOLD_PRE_FOUNDATION_DATA`) e o de maior risco de regressão silenciosa caso o hardcode
  seja perdido em uma refatoração futura.

## Nível 1 — Contagem de linhas

```sql
SELECT
  'legado' AS origem, COUNT(*) AS qtd_linhas
FROM `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
WHERE invoice_month = @periodo
UNION ALL
SELECT
  'novo' AS origem, COUNT(*) AS qtd_linhas
FROM `<projeto_novo>.billing_gold.tb_gcp_gold_pre_foundation`
WHERE invoice_month = @periodo
```

Threshold: qualquer diferença de contagem (`!= 0`) é `FAIL` — esta tabela não tem motivo
legítimo para ter linha duplicada ou perdida entre ambientes idênticos.

## Nível 2 — Diff agregado por dimensão de negócio

Dimensões escolhidas: `projeto_id`, `servico_nome`, `cc_codigo` — são as três chaves de
agregação mais usadas downstream nos dashboards Looker Studio e no chargeback por centro de
custo, então qualquer divergência nessas dimensões tem impacto financeiro direto e visível para
as áreas consumidoras.

```sql
WITH legado AS (
  SELECT
    projeto_id, servico_nome, cc_codigo, invoice_month,
    ROUND(SUM(custo), 2) AS custo_total,
    ROUND(SUM(creditos), 2) AS creditos_total,
    ROUND(SUM(credito_cud), 2) AS credito_cud_total,
    ROUND(SUM(ajuste), 2) AS ajuste_total,
    ROUND(SUM(custo_suporte), 2) AS custo_suporte_total,
    ROUND(SUM(credito_suporte), 2) AS credito_suporte_total
  FROM `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
  WHERE invoice_month = @periodo
  GROUP BY 1, 2, 3, 4
),
novo AS (
  SELECT
    projeto_id, servico_nome, cc_codigo, invoice_month,
    ROUND(SUM(custo), 2) AS custo_total,
    ROUND(SUM(creditos), 2) AS creditos_total,
    ROUND(SUM(credito_cud), 2) AS credito_cud_total,
    ROUND(SUM(ajuste), 2) AS ajuste_total,
    ROUND(SUM(custo_suporte), 2) AS custo_suporte_total,
    ROUND(SUM(credito_suporte), 2) AS credito_suporte_total
  FROM `<projeto_novo>.billing_gold.tb_gcp_gold_pre_foundation`
  WHERE invoice_month = @periodo
  GROUP BY 1, 2, 3, 4
)
SELECT
  COALESCE(l.projeto_id, n.projeto_id) AS projeto_id,
  COALESCE(l.servico_nome, n.servico_nome) AS servico_nome,
  COALESCE(l.cc_codigo, n.cc_codigo) AS cc_codigo,
  COALESCE(l.invoice_month, n.invoice_month) AS invoice_month,
  l.custo_total AS custo_legado, n.custo_total AS custo_novo,
  ROUND(COALESCE(n.custo_total, 0) - COALESCE(l.custo_total, 0), 2) AS diff_custo,
  l.creditos_total AS creditos_legado, n.creditos_total AS creditos_novo,
  ROUND(COALESCE(n.creditos_total, 0) - COALESCE(l.creditos_total, 0), 2) AS diff_creditos,
  l.credito_cud_total AS credito_cud_legado, n.credito_cud_total AS credito_cud_novo,
  l.ajuste_total AS ajuste_legado, n.ajuste_total AS ajuste_novo,
  ROUND(COALESCE(n.ajuste_total, 0) - COALESCE(l.ajuste_total, 0), 2) AS diff_ajuste,
  l.custo_suporte_total AS custo_suporte_legado, n.custo_suporte_total AS custo_suporte_novo,
  l.credito_suporte_total AS credito_suporte_legado, n.credito_suporte_total AS credito_suporte_novo
FROM legado l
FULL OUTER JOIN novo n
  ON l.projeto_id = n.projeto_id
  AND l.servico_nome = n.servico_nome
  AND l.cc_codigo = n.cc_codigo
  AND l.invoice_month = n.invoice_month
WHERE
  ABS(COALESCE(n.custo_total, 0) - COALESCE(l.custo_total, 0)) > 0.01
  OR ABS(COALESCE(n.creditos_total, 0) - COALESCE(l.creditos_total, 0)) > 0.01
  OR ABS(COALESCE(n.credito_cud_total, 0) - COALESCE(l.credito_cud_total, 0)) > 0.01
  OR ABS(COALESCE(n.ajuste_total, 0) - COALESCE(l.ajuste_total, 0)) > 0.01
  OR ABS(COALESCE(n.custo_suporte_total, 0) - COALESCE(l.custo_suporte_total, 0)) > 0.01
  OR ABS(COALESCE(n.credito_suporte_total, 0) - COALESCE(l.credito_suporte_total, 0)) > 0.01
ORDER BY ABS(diff_custo) DESC
```

**Threshold explícito**: diferença absoluta > R$ 0,01 em qualquer uma das 6 métricas
financeiras (`custo`, `creditos`, `credito_cud`, `ajuste`, `custo_suporte`, `credito_suporte`) =
falha. Não usar threshold percentual aqui — célula de agregação fina (projeto × serviço × CC)
pode ter base pequena, tornando diferença percentual enganosa (R$ 1.000 de diferença em uma
célula de R$ 1.000.000 é 0,1%, mas R$ 1.000 de diferença sozinho já é inaceitável em billing).

**Atenção ao mês `2023-12-01`**: validar esta query separadamente para esse período, comparando
também o `custo_gold`/`creditos_gold` retornados por `CHECK_GOLD_PRE_FOUNDATION_DATA` — o ajuste
hardcoded (`+400541.37 - 699496.39 - 35914.76` e `-28330.58`) precisa aparecer idêntico nos dois
ambientes; se o dual-run mostrar esse mês com `ajuste_total = 0` no novo, é sinal de que o
hardcode foi perdido (`FAIL` imediato, sem precisar de threshold).

## Nível 3 — Registros exclusivos (full outer join por chave de grain)

Chave de grain escolhida: não há um ID técnico de linha nesta tabela (não há `transaction_id`),
então a chave de negócio precisa combinar todas as dimensões que discriminam uma linha,
incluindo `usage_date` (granularidade diária dentro do `invoice_month`) e `sku_id` (uma SKU pode
se repetir em datas diferentes para o mesmo projeto/serviço).

```sql
WITH legado_grain AS (
  SELECT
    CONCAT(
      COALESCE(projeto_id, ''), '|',
      COALESCE(CAST(usage_date AS STRING), ''), '|',
      COALESCE(servico_id, ''), '|',
      COALESCE(sku_id, ''), '|',
      COALESCE(cc_codigo, '')
    ) AS chave_grain
  FROM `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
  WHERE invoice_month = @periodo
),
novo_grain AS (
  SELECT
    CONCAT(
      COALESCE(projeto_id, ''), '|',
      COALESCE(CAST(usage_date AS STRING), ''), '|',
      COALESCE(servico_id, ''), '|',
      COALESCE(sku_id, ''), '|',
      COALESCE(cc_codigo, '')
    ) AS chave_grain
  FROM `<projeto_novo>.billing_gold.tb_gcp_gold_pre_foundation`
  WHERE invoice_month = @periodo
)
SELECT
  COALESCE(l.chave_grain, n.chave_grain) AS chave_grain,
  CASE
    WHEN n.chave_grain IS NULL THEN 'só existe no legado'
    WHEN l.chave_grain IS NULL THEN 'só existe no novo'
  END AS situacao
FROM legado_grain l
FULL OUTER JOIN novo_grain n USING (chave_grain)
WHERE l.chave_grain IS NULL OR n.chave_grain IS NULL
```

**Risco conhecido de falso positivo nesta chave**: a linha hardcoded de `2023-12-01`
(`projeto_id = ''`, `sku_id = '5AB4-0B3B-9EEC'`, `servico_id = 'A656-35D2-EF7F'`) é uma constante
fixa no SQL — se aparecer como "exclusiva" de um lado, não é bug de pipeline, é sinal de que o
filtro `WHERE invoice_month = '{{invoice_month}}'` da subquery hardcoded não disparou (ex.:
formato de data diferente) — investigar essa linha separadamente antes de generalizar a causa
para o resto da tabela.

**Threshold**: zero registros exclusivos não explicados = único resultado aceitável. Qualquer
linha que apareça aqui exige explicação registrada (ex.: linha vinda de uma das 5 fontes
externas que estava temporariamente indisponível em um dos ambientes no momento da extração) —
nunca atribuir a "timing" sem confirmar.

## Nível 4 — Hash de linha (colunas de detalhe)

Útil aqui porque o grain (Nível 3) não cobre colunas como `labels`, `tags`, `system_labels`,
`workstream`, `iniciativa`, `diretoria_n1/n2`, `gerencia_n3`, `gestor`, `area_n4`, `cc_nome` —
todas resolvidas por `JOIN`s com tabelas de mapeamento (`omnicloud_contas_raw`,
`tb_gcp_marketplace_services`, `centro_de_custo_raw`) que podem ter sido atualizadas entre a
execução do legado e a do novo, mesmo com o SQL idêntico.

```sql
WITH legado AS (
  SELECT
    CONCAT(
      COALESCE(projeto_id, ''), '|', COALESCE(CAST(usage_date AS STRING), ''), '|',
      COALESCE(servico_id, ''), '|', COALESCE(sku_id, ''), '|', COALESCE(cc_codigo, '')
    ) AS chave_grain,
    TO_BASE64(MD5(TO_JSON_STRING(t))) AS hash_linha
  FROM `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation` t
  WHERE invoice_month = @periodo
),
novo AS (
  SELECT
    CONCAT(
      COALESCE(projeto_id, ''), '|', COALESCE(CAST(usage_date AS STRING), ''), '|',
      COALESCE(servico_id, ''), '|', COALESCE(sku_id, ''), '|', COALESCE(cc_codigo, '')
    ) AS chave_grain,
    TO_BASE64(MD5(TO_JSON_STRING(t))) AS hash_linha
  FROM `<projeto_novo>.billing_gold.tb_gcp_gold_pre_foundation` t
  WHERE invoice_month = @periodo
)
SELECT
  l.chave_grain,
  l.hash_linha AS hash_legado,
  n.hash_linha AS hash_novo
FROM legado l
JOIN novo n USING (chave_grain)
WHERE l.hash_linha != n.hash_linha
```

Se este nível mostrar divergência com Nível 2/3 limpos, a causa está em coluna de detalhe
(`labels`/`tags`/`system_labels`/hierarquia de CC) — abrir a linha específica coluna a coluna
para achar qual campo mudou antes de concluir qualquer coisa.

## Nível 5 — Diff de schema

```sql
SELECT column_name, data_type, ordinal_position
FROM `gglobo-billing-hdg-prd.billing_gold.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'tb_gcp_gold_pre_foundation'
ORDER BY ordinal_position
```

Comparar contra a mesma query no projeto novo. A lista de colunas do `INSERT INTO` (32 colunas,
visível em `INSERT_GOLD_PRE_FOUNDATION_DATA`) é idêntica entre legado e migrado por construção
(mesmo SQL — confirmado na revisão estática), então este nível deve dar `PASS` automático **se**
a tabela de destino no ambiente novo for criada com o mesmo DDL do legado. Não assumir isso:
conferir o Terraform/DDL da tabela `tb_gcp_gold_pre_foundation` no ambiente novo antes do
dual-run, em especial os tipos de `labels`/`tags`/`system_labels` (`ARRAY<STRUCT<...>>`) — é o
ponto mais comum de divergência de schema nessa tabela.

## Veredito de sign-off (dual-run real)

Não aplicável ainda — não execute estas queries como se fossem validação real. Critérios de
sign-off de cutour (`>= 2 ciclos de fechamento mensal consecutivos`, `zero INVESTIGATE aberto`,
`volume real de produção`) seguem os definidos em `qa-reconciliation.md` e só serão avaliados
quando houver ambiente de dual-run real e estas queries forem promovidas a testes executáveis em
`pipelines/gold_pre_foundation/tests/reconciliation/test_row_count_parity.py`,
`test_aggregate_parity.py` e `test_schema_parity.py`.
