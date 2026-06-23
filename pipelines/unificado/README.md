# unificado_pipeline

Camada Unificado do medalhão moderno `gcp_labels`: consolida o resultado
multicloud (GCP, Tsuru, DBaaS) lendo `billing_gold.vw_gcp_unificada_labels`,
enriquece com mapeamentos de produto/squad/app de negócio (plataformas de
vídeo, Globoplay) e grava em
`billing_gold.tb_gcp_tsuru_dbaas_unificada_labels`. Antes do load, valida que
a soma por provedor bate com 3 fontes "gold" independentes (GCP, Tsuru,
DBaaS).

Migrado de `gcp_labels/services/gcp_unificado_label_service.py` (legado), com
paridade funcional confirmada.

## Variáveis de ambiente

Ver `.env.example`. Resumo: `GCP_PROJECT`, `GCP_GOLD_UNIFICADO_LABEL_TABLE`,
`COST_VALIDATION_LIMIT`.

## ⚠️ Achado aberto a validar com o usuário antes do cutover desta camada

Confirmado por leitura de `gcp_labels/main.py` (legado): o branch
`pre_dbaas_tsuru` do orquestrador (modo padrão de produção, disparado pela
Cloud Function `gcp-cost-with-labels` via `gcp-workflow-labels-trigger`)
executa Silver → Gold Pre-Foundation → Gold Foundation → Gold, mas **não**
chama a camada Unificado. Apenas os branches `layer=None` (pipeline completa)
e `layer="unificado"` (execução isolada) o fazem — nenhum dos dois é o modo de
execução diária agendada. Ou seja, **`tb_gcp_tsuru_dbaas_unificada_labels`
pode não estar sendo atualizada automaticamente em produção hoje**.

Esta migração não decide se isso é um bug do legado a corrigir ou um
comportamento intencional (talvez a camada seja disparada por outro job/cron
não identificado nesta migração) — ver `CLAUDE.md` na raiz do repositório.
Antes de decidir o agendamento desta camada no novo ambiente, confirmar com o
usuário a origem real das atualizações de `tb_gcp_tsuru_dbaas_unificada_labels`
em produção.

## Outros achados de paridade (preservados fielmente, não corrigidos)

- **Sem `labels` de custo**: diferente de todas as outras camadas do
  medalhão, este service nunca passa `labels=` ao `exec_query` — os jobs
  desta camada não são tagueados para auditoria de custo por camada.
- **`diff_total` soma diferenças com sinal, não valores absolutos**: em
  `check_result_query`, uma divergência de +X num provedor pode ser
  cancelada por uma divergência de -X em outro provedor/coluna antes da
  comparação com `COST_VALIDATION_LIMIT`, mascarando duas divergências reais.
  Ver teste `test_opposite_sign_diffs_across_providers_cancel_out`.

## Dependências externas fora de escopo

`SELECT_GOLD_UNIFICADO_DATA` lê de `billing_gold.vw_gcp_unificada_labels` e de
`external_tables.tb_plataformas_de_video_produto_squad`/
`external_tables.tb_globoplay_produto_squad`. `CHECK_GOLD_UNIFICADO_DATA`
compara contra `billing_gold.vw_gcp_tsuru_usage_metering_gold`,
`billing_gold.tb_rateio_dbaas_billing` e
`billing_gold.tb_gcp_billing_projeto_ar_label`. Nenhuma dessas tabelas/views
foi migrada nesta entrega — apenas referenciadas via SQL.

## Uso

```python
from unificado_pipeline.services.unificado_service import UnificadoService

service = UnificadoService(bypass_validation=False)
result = service.load_gold_unificado_data(invoice_month="2024-04-01")
```

Ou via entry point mínimo:

```bash
uv run python -m unificado_pipeline.main 2024-04-01
```

## Testes

```bash
uv run pytest pipelines/unificado/tests
```
