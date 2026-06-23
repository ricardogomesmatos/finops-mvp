# Troubleshooting — finops-billing

> Lido para escrever este documento: `config/base.py` (`BaseEnvConfigs.validate`),
> `adapters/bigquery.py` (`BigQueryAdapter.exec_query`/`insert_rows`, tratamento de exceção),
> `secrets/secret_manager.py` (`get_secret_json`), `services/*.py` das 5 camadas (lógica de
> `check_*`/validação de custo). Toda causa listada abaixo nasce de uma exceção/comportamento
> real visto no código ou reproduzido em execução local (`uv run pytest -q` → 101 passed) —
> nenhum sintoma genérico de "pipeline de dados" foi inventado.

## Catálogo de problemas

| Sintoma | Causa provável | Diagnóstico | Solução |
|---|---|---|---|
| Processo encerra imediatamente com `sys.exit(1)` e log `"Please set the environment variable <X>"` | Variável de ambiente obrigatória ausente. `BaseEnvConfigs.validate()` (`libs/billing_common/src/billing_common/config/base.py:43-55`) verifica `expected_envs` e mata o processo antes de qualquer lógica de negócio. | Ler a mensagem de log — ela lista exatamente qual(is) variável(eis) falta(m). Comparar com `.env.example` da camada em questão. | Exportar a variável faltante no shell (`export NOME=valor` / `$env:NOME = "valor"` no PowerShell) ou completar o `.env` e recarregá-lo antes de rodar. |
| `RuntimeError: BQ query failed [<mes>]: <mensagem da API>` | `BigQueryAdapter.exec_query` (`bigquery.py:58-65`) encapsula qualquer exceção do client BigQuery em `RuntimeError`, incluindo erros de sintaxe SQL, permissão e tabela inexistente. | Ler a mensagem original encapsulada (`<mensagem da API>` no final do texto) — ela aponta a causa real da API do BigQuery (ex.: `403 Access Denied`, `404 Not found: Table`, `400 Syntax error`). | Depende da causa real: `403` → revisar IAM/ADC (`gcloud auth application-default login`); `404` → confirmar nome de tabela no `.env`/env var (erro comum: apontar `GCP_SILVER_LABEL_TABLE` para `gcp_billing_silver` sem `_label`); `400` → reportar como bug do template Jinja (não deveria ocorrer em produção, já que os SQLs são fixos e testados). |
| `status: failed`, `details` contém `"diff: <valor grande>"` ou `"Os custos totais não estão batendo por: <valor>"` | Validação de paridade de custo bloqueou o load — `cost_delta`/`diff_total` excedeu `COST_VALIDATION_LIMIT` (default 15000). Confirmado em `silver_label_service.py:125-126`, `gold_pre_foundation_service.py:129-130`, `gold_service.py:109-110`, `unificado_service.py:168-173`. | Ler o `details` completo — contém os totais comparados (ex.: `total_silver` vs `total_raw`). Rodar a query de `CHECK_*`/`check_result_query` manualmente no BigQuery Console para investigar de onde vem a divergência (ex.: dados ainda não chegaram na fonte, atraso de partição). | Se a divergência for legítima e esperada (ex.: ajuste financeiro conhecido), rodar novamente com `bypass_validation=True` — ver `docs/OPERACAO.md` seção 3. Se for inesperada, **não usar bypass** — investigar a fonte primeiro (provável atraso de dados upstream ou mudança de schema). |
| Camada Unificado nunca bloqueia mesmo com divergência grande visível manualmente | **Bug de paridade confirmado por leitura de código**: `diff_total` em `unificado_service.py:163-166` soma as diferenças **com sinal** (sem `abs()`). Uma divergência positiva num provedor pode ser cancelada matematicamente por uma negativa em outro antes da comparação com `COST_VALIDATION_LIMIT`. | Comparar manualmente cada `dict_column_diff[provedor][coluna]` (logado/disponível no objeto, não apenas o total) em vez de confiar só no resultado agregado de `diff_total`. | Não há correção automática — é comportamento herdado do legado, preservado fielmente nesta migração (decisão documentada, não bug introduzido aqui). Se uma correção for decidida, ela precisa ser deliberada e registrada (mudaria paridade comportamental com o legado) — não fazer silenciosamente. |
| `tb_gcp_tsuru_dbaas_unificada_labels` parece "parada", sem atualização recente | **Achado aberto, não resolvido**: no legado, o branch `pre_dbaas_tsuru` (modo padrão de produção do orquestrador `gcp_labels/main.py`) **não chama** a camada Unificado. Só os branches `layer=None` ou `layer="unificado"` o fazem. | Confirmar se existe algum outro job/cron (fora deste repositório, possivelmente fora do `gcp_labels/main.py`) que dispara a camada Unificado isoladamente. Verificar a data do último `invoice_month` presente na tabela de destino. | Não decidir sozinho. Este é um achado aberto documentado em `CLAUDE.md` e nos READMEs do pipeline — escalar para o time/owner do legado antes de assumir que é bug ou de tentar "corrigir" agendando a camada de forma autônoma. |
| `RuntimeError: Empty check cost data query result` | A query de `CHECK_*` não retornou nenhuma linha — geralmente porque a tabela de origem está vazia para o `invoice_month`/janela de partição pedida (ex.: dados ainda não carregados, ou `invoice_month` no futuro). Confirmado em `silver_label_service.py:92-93`, `gold_pre_foundation_service.py:107-108`, `gold_service.py:87-88`. | Rodar a query `SELECT_*`/`CHECK_*` manualmente no BigQuery Console para o mesmo `invoice_month` e confirmar se a fonte tem dados. | Aguardar a fonte popular (problema upstream) ou confirmar que o `invoice_month` passado é o correto. Não é um bug do pipeline — é ausência de dado de origem. |
| `ValueError: time data '<algo>' does not match format '%Y-%m-%d'` (ou `status: failed` com mensagem equivalente) | `invoice_month` passado em formato errado (ex.: `04/2024`, `2024-4-1` sem zero-padding, ou string vazia). Todas as camadas validam com `datetime.strptime(invoice_month, "%Y-%m-%d")` antes de qualquer query. | Confirmar o argumento exato passado na CLI ou no payload que disparou a execução. | Sempre usar `YYYY-MM-DD` com o dia fixo em `01` (primeiro dia do mês) — é o padrão usado em todo o medalhão, mesmo que a granularidade de negócio seja mensal. |
| Linha duplicada para o mesmo `invoice_month` numa tabela de destino | Não deveria ocorrer em uso normal — toda camada faz `DELETE WHERE invoice_month = ...` antes do `INSERT` (idempotência por design). Se ocorreu, é provável que duas execuções tenham rodado **concorrentemente** para o mesmo `invoice_month` (sem lock entre processos) — uma pode ter inserido entre o `DELETE` e o `INSERT` da outra. | Verificar `INFORMATION_SCHEMA.JOBS_BY_PROJECT` por jobs com `labels.finops-workflow-layer = '<camada>'` rodando no mesmo intervalo de tempo (lembrar que a camada Unificado não tem esse label). | Apagar manualmente o `invoice_month` afetado e reprocessar uma única vez, garantindo que não há outra execução concorrente em andamento (ver checklist de `docs/OPERACAO.md`). Considerar, como melhoria futura, adicionar lock distribuído se execuções concorrentes forem um risco real (ex.: Cloud Scheduler + retry automático disparando duas vezes). |
| Job de BigQuery "trava" (não retorna) | `exec_query` chama `job.result(timeout=None)` (`bigquery.py:61`) — **sem timeout**, o processo Python aguarda indefinidamente o job do BigQuery terminar, mesmo que o job esteja processando um volume anormalmente grande de dados ou preso em fila de slots. | Verificar o `job_id` logado em "BQ job submitted: `<job_id>`" no BigQuery Console → `Job History` → checar `Bytes processed`/status real do job (pode estar `RUNNING` legitimamente, só lento). | Se o job real estiver travado/anormalmente lento no BigQuery (não é o processo Python que travou, é o job mesmo), cancelar via `bq cancel <job_id>` e investigar causa (ex.: contenção de slots, partição mal otimizada). Não há retry automático nem timeout configurável no código atual — possível melhoria futura. |
| `uv sync --all-packages` falha ou pipeline novo não é resolvido pelo workspace | Novo pipeline criado sem seguir o layout `src/<nome>_pipeline/` ou sem declarar `billing-common = { workspace = true }` no `[tool.uv.sources]` do seu `pyproject.toml`. | Comparar a estrutura do novo pipeline com `pipelines/silver/pyproject.toml` (referência). | Corrigir o `pyproject.toml` do novo pipeline conforme o passo 2 de "Adicionando um novo pipeline" no `README.md` raiz, depois rodar `uv sync --all-packages` novamente. |
| CI (`.gitlab-ci.yml`) passa mesmo com bug em `gold`, `gold_pre_foundation`, `gold_foundation` ou `unificado` | **Lacuna de cobertura confirmada por leitura**: `.gitlab-ci.yml` só define jobs `pytest-billing-common` e `pytest-silver-pipeline` no estágio `test`. Não há job de teste para as outras 4 camadas migradas — os testes existem localmente (`pipelines/<camada>/tests/`) mas **não rodam no pipeline de CI**. | Ler `.gitlab-ci.yml` — confirma que só 2 dos 5 pacotes de `pipelines/`+`libs/` têm job de teste dedicado. | Adicionar um job `pytest-<nome>-pipeline` por pacote faltante, seguindo o padrão exato dos dois jobs existentes. Até essa lacuna ser fechada, um bug introduzido em qualquer uma dessas 4 camadas **não será detectado pelo CI** — só por execução manual de `uv run pytest pipelines/<camada>/tests`. |
| Deploy "falhou" para uma das 5 camadas do medalhão | Não há processo de deploy para nenhum componente deste repositório — não existe Terraform instanciado, Dockerfile nem pipeline de CD para `silver`, `gold_pre_foundation`, `gold_foundation`, `gold` ou `unificado`. | Confirmar em `terraform/environments/{dev,prod}/` — só existem `provider.tf`, `variables.tf` e `outputs.tf` (vazio), sem nenhum módulo instanciado. | Não é um erro de execução, é ausência de escopo (ver `CLAUDE.md` e `docs/DEPLOYMENT.md`). Se o objetivo é colocar uma dessas camadas em produção, o trabalho de Terraform/Cloud Function ainda precisa ser feito — não tentar improvisar um deploy manual sem alinhar com o time. |

## Monitoramento

### Logs (Cloud Logging — quando houver deploy real)

Todos os pipelines emitem logs JSON estruturados via `build_logger` (stdout), com os campos
`severity`, `message`, `timestamp`, `logger` (e `exception` quando há traceback). Quando rodando
em Cloud Run/Cloud Function, o Cloud Logging faz parsing automático desse JSON.

Filtros úteis (sintaxe Cloud Logging, ⚠️ a confirmar nome exato do recurso/serviço quando o
deploy de cada camada existir):

```
# Todos os logs de uma camada específica
jsonPayload.logger="silver_pipeline.silver_label_service"

# Apenas erros
severity>=ERROR

# Falhas de validação de custo (bloqueios de paridade)
jsonPayload.message:"Failed for invoice_month"

# Jobs BigQuery submetidos por uma camada (para correlacionar com Job History)
jsonPayload.message:"BQ job submitted"
```

### Custo por job/camada (BigQuery `INFORMATION_SCHEMA`)

Todas as camadas exceto **Unificado** marcam seus jobs com `labels` via `QueryJobConfig` —
permite auditoria de custo por camada:

```sql
SELECT
  labels,
  SUM(total_bytes_processed) / POW(1024, 3) AS gb_processados,
  COUNT(*) AS qtd_jobs
FROM `region-us-east1`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND EXISTS (SELECT 1 FROM UNNEST(labels) WHERE key = 'finops-workflow-layer')
GROUP BY labels
ORDER BY gb_processados DESC
```

Labels reais usados, confirmados por leitura de cada service:

| Camada | `finops-workflow` | `finops-workflow-layer` |
|---|---|---|
| Silver | `gcp` | `gcp-silver` |
| Gold Pre-Foundation | `gcp` | `gcp-gold-pre-foundation` |
| Gold Foundation | `gcp` | `gcp-gold` (⚠️ ver atenção abaixo) |
| Gold | `gcp` | `gcp-gold` |
| Unificado | — (nenhum label, confirmado) | — |

⚠️ **Atenção — achado de paridade confirmado por leitura**: `gold_foundation_service.py:50`
define `self.labels = {"finops-workflow": "gcp", "finops-workflow-layer": "gcp-gold"}` — o
**mesmo valor** `gcp-gold` usado pela camada Gold (`gold_service.py:59`), não um valor próprio
como `gcp-gold-foundation`. Isso significa que a query de custo por `labels` acima **agrupa Gold
Foundation e Gold sob a mesma chave** em `INFORMATION_SCHEMA.JOBS_BY_PROJECT` — não é possível
hoje segregar o custo de BigQuery dessas duas camadas apenas pelo label
`finops-workflow-layer`. Replicado fielmente do legado (não corrigido nesta migração); considerar
como melhoria futura se a segregação de custo por camada for um requisito de FinOps.

### Dashboards existentes

⚠️ **A confirmar com o time**: não há, neste repositório, nenhuma definição de dashboard
Looker Studio (são recursos externos ao código). O `CLAUDE.md` e os READMEs de camada confirmam
que `tb_gcp_billing_foundation_labels_dashboard` e `tb_gcp_billing_projeto_ar_label` alimentam
dashboards Looker Studio, mas a definição/URL desses dashboards não está versionada aqui.

## Lacunas de teste conhecidas (relevantes para troubleshooting)

- `gold_pre_foundation` não tem baseline de teste herdada do legado (testes escritos do zero
  contra o comportamento real, conforme `tests/reconciliation/README.md`).
- `gold_foundation` não tem baseline de teste legado (o legado só testava Silver e Gold).
- `gold` tem baseline de teste legado **desatualizada** — `gcp_labels/tests/test_gold_label_service.py`
  testa uma versão antiga do `SELECT_GOLD_DATA` que lia diretamente da Silver, não da
  Gold Pre-Foundation como o template atual faz.
- Nenhuma camada tem teste de integração real contra BigQuery (todas usam
  `unittest.mock.patch`) — um erro de sintaxe SQL real só seria detectado em execução manual
  contra um projeto GCP real, nunca pelo `pytest`.
- Não existe dual-run/reconciliação real executada contra produção ainda — o que existe em
  `pipelines/gold_pre_foundation/tests/reconciliation/README.md` é um **rascunho de queries**,
  explicitamente marcado como "NÃO EXECUTÁVEL" até haver ambiente de dual-run real.
