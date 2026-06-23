# finops-billing

Repositório destino da modernização do ambiente legado **`gcp-billing`** (consolidação de billing multicloud da Globo — GCP, AWS, Azure, OCI, Tsuru, DBaaS — usado para chargeback financeiro e dashboards Looker Studio).

## Repositório de origem (legado)

`~/gcp-billing` (local: `C:\Users\ricar\gcp-billing`). Sempre que for inventariar, comparar ou migrar lógica, ler o código real desse repositório — não assumir comportamento pela documentação.

## Prioridade da migração

A prioridade é a arquitetura medalhão de **5 camadas** do pipeline moderno `gcp_labels`:

```
silver_label (gcp_billing_silver_label)            -- migrado: pipelines/silver
  → gold_pre_foundation (tb_gcp_gold_pre_foundation) -- migrado: pipelines/gold_pre_foundation
  → gold_foundation (tb_gcp_billing_foundation_labels[_dashboard]) -- migrado: pipelines/gold_foundation
  → gold (tb_gcp_billing_projeto_ar_label)           -- migrado: pipelines/gold
  → unificado (tb_gcp_tsuru_dbaas_unificada_labels)  -- migrado: pipelines/unificado
```

As 5 camadas têm código Python migrado (services + templates SQL + testes), com paridade comportamental confirmada por leitura do legado. **Ainda fora de escopo**: Terraform de deploy (Cloud Function/Cloud Run + Scheduler) para essas 5 camadas, dual-run/reconciliação real contra produção (gate do `qa-reconciliation`) e cutover do orquestrador (`gcp_labels/main.py`) — o novo repositório não replica esse orquestrador único ainda, cada camada tem um `main.py` próprio e independente (ver READMEs de cada `pipelines/<camada>/`).

Deploy real do legado: Cloud Function `gcp-cost-with-labels` (Gen2), disparada diariamente via `gcp-workflow-labels-trigger` + Cloud Scheduler. Já provisionada em dev e prod.

**Fora de prioridade** (não migrar a menos que pedido explicitamente): a tabela `billing_silver.gcp_billing_silver` (sem `_label`) e o pipeline legado `gcp_raw_to_silver` → `gcp_silver_to_gold` → `gcp_gold_to_month`, orquestrado via Cloud Workflows (`workflow/workflow_gcp.yaml`) e só provisionado em prod. Tratar como candidato a descontinuação após confirmar ausência de consumidores.

**Achado aberto a validar com o usuário antes de migrar a camada Gold/Unificado**: no `gcp_labels/main.py`, o branch `pre_dbaas_tsuru` (modo padrão de produção) não chama a camada `unificado` — `tb_gcp_tsuru_dbaas_unificada_labels` pode não estar sendo atualizada pelo fluxo automático diário. Confirmar se é intencional ou bug do legado antes de decidir se a migração replica ou corrige esse comportamento.

## Débitos técnicos do legado a NÃO repetir aqui

1. `utils/` e `adapters/bigquery_adapter.py` duplicados (quase) idênticos em cada Cloud Function — extrair para `libs/billing_common`.
2. Terraform assimétrico entre dev (modular) e prod (`main.tf` monolítico) — dev e prod devem compartilhar os mesmos módulos.
3. Ausência de módulos Terraform reutilizáveis para recursos repetidos (Cloud Function, dataset, tabela).
4. SQL de views divergente entre ambientes — única fonte via `templatefile()`.
5. Pipelines legados sempre provisionados, sem flag de habilitação/desabilitação.
6. `outputs.tf` vazio — sempre exportar IDs/URLs úteis.

Detalhe completo de cada item e o porquê: `.claude/agents/gcp-data-engineer.md`.

## Estrutura alvo (referência, evoluir conforme o código real for criado)

```
libs/billing_common/      # adapters, logger, env_configs base, date utils — usado por todos os pipelines
pipelines/<nome>/         # um por camada/domínio migrado, com services/ + bigquery_views/ + tests/
terraform/modules/        # módulos reutilizáveis (bigquery_dataset, bigquery_table, cloud_function, ...)
terraform/environments/   # dev e prod chamando os MESMOS módulos, variando só tfvars/backend.conf
```

## Agentes deste projeto

- **`gcp-data-engineer`** (`.claude/agents/gcp-data-engineer.md`) — conduz a migração: inventário, extração de código comum, Terraform, implementação dos pipelines.
- **`qa-reconciliation`** (`.claude/agents/qa-reconciliation.md`) — valida de forma independente a paridade legado vs. novo antes de qualquer cutover ou decomissionamento. Gate obrigatório, não opcional.

Estratégia de migração em 6 fases (inventário → mapeamento de dependências → extração de código comum → migração com paridade → cutover controlado → decomissionamento) — detalhada no `gcp-data-engineer`.
