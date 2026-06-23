# Runbook operacional — finops-billing

> Lido para escrever este documento: mesmo conjunto de `services/*.py`, `adapters/bigquery.py`,
> `config/base.py` e `.gitlab-ci.yml`/Terraform usados em `docs/TROUBLESHOOTING.md`. Cada
> runbook abaixo cobre um cenário real possível neste código (confirmado por leitura), não um
> cenário genérico de "pipeline de dados quebrado".

Formato de cada runbook: **Sintoma → Diagnóstico → Ação corretiva → Validação → Escalonamento**.

---

## Runbook 1 — Pipeline (camada do medalhão) falhando

**Sintoma**: `uv run python -m <camada>_pipeline.main <invoice_month>` retorna código de saída
1, ou o retorno programático do `service.load_*` é `{"status": "failed", "details": "..."}`.

**Diagnóstico**:
1. Ler o `details` do retorno — ele contém a mensagem de exceção real (capturada pelo `try/except`
   genérico em cada `load_*_data`, ex. `silver_label_service.py:62-64`).
2. Classificar a causa pelo texto:
   - Contém `"environment variable"` → variável de ambiente faltante (ver Runbook 4).
   - Contém `"BQ query failed"` → erro do client BigQuery (sintaxe, permissão, tabela
     inexistente) — ver Runbook 3.
   - Contém `"diff:"` ou `"não estão batendo por"` → bloqueio de validação de paridade de custo
     (ver Runbook 5).
   - Contém `"does not match format"` → `invoice_month` em formato inválido.
   - Contém `"Empty check cost data query result"` → fonte de dados vazia para o período.

**Ação corretiva**:
- Variável de ambiente: completar `.env`/exportar a variável faltante e rodar de novo.
- Erro de BigQuery: corrigir IAM/nome de tabela conforme a mensagem real da API (ver Runbook 3).
- Bloqueio de paridade: investigar a fonte antes de decidir entre aguardar dados ou usar
  `bypass_validation=True` (ver Runbook 5 e `docs/OPERACAO.md` seção 3).
- Formato de data: corrigir para `YYYY-MM-DD` (primeiro dia do mês).
- Fonte vazia: confirmar se os dados upstream já foram carregados para o período; se sim, é bug
  a investigar nas camadas anteriores do medalhão.

**Validação**: re-executar a mesma camada para o mesmo `invoice_month` e confirmar
`status: success`. Validar contagem de linhas e soma de custo na tabela de destino (ver
`docs/OPERACAO.md` seção 4.2).

**Escalonamento**: se a causa não for nenhuma das listadas acima (ex.: traceback inesperado,
`AttributeError`, `TypeError`), é provável bug de código introduzido recentemente — abrir
incidente com o time responsável pela camada (`gcp-data-engineer`) com o `details` completo e o
`invoice_month` usado.

---

## Runbook 2 — Job travado (não retorna)

**Sintoma**: o processo Python fica em execução por tempo anormalmente longo, sem log de "BQ
job completed" aparecer.

**Diagnóstico**:
1. `BigQueryAdapter.exec_query` chama `job.result(timeout=None)` (`bigquery.py:61`) — **não há
   timeout no código**. O processo aguardará indefinidamente o job do BigQuery.
2. Localizar o `job_id` no log "BQ job submitted: `<job_id>` [`<invoice_month>`]".
3. No BigQuery Console → Job History → buscar pelo `job_id` → verificar status real
   (`RUNNING`, `PENDING` em fila de slots, ou já `DONE` com erro não propagado — improvável, mas
   verificar).

**Ação corretiva**:
- Se o job estiver genuinamente processando um volume grande (`RUNNING`, bytes processados
  crescendo): aguardar, ou avaliar se a query/partição pode ser otimizada.
- Se o job estiver preso em fila de slots (`PENDING` por muito tempo): verificar contenção de
  slots no projeto/reservation; considerar rodar fora de horário de pico.
- Se necessário interromper: `bq cancel <job_id>` (cancela no BigQuery) **e** `Ctrl+C` no
  processo local (interrompe o Python — lembrar que um `Ctrl+C` isolado não cancela o job real,
  ver `docs/OPERACAO.md` seção 6).

**Validação**: confirmar no Job History que o job está `DONE` (sucesso ou cancelado) e que não
há jobs duplicados/concorrentes para o mesmo `invoice_month` e camada.

**Escalonamento**: se jobs travarem repetidamente, é candidato a melhoria de código (adicionar
timeout configurável em `BigQueryAdapter.exec_query`) — abrir como débito técnico com o
`gcp-data-engineer`, não como correção ad-hoc em produção.

---

## Runbook 3 — Falha de autenticação/permissão

**Sintoma**: `RuntimeError: BQ query failed [...]: 403 Access Denied: ...` ou erro de
credenciais ao instanciar `BigQueryAdapter`/`bigquery.Client`.

**Diagnóstico**:
1. Confirmar se há ADC válida no ambiente: `gcloud auth application-default print-access-token`.
2. Confirmar que o projeto ativo (`gcloud config get-value project`) corresponde ao
   `GCP_PROJECT` configurado na env var da camada.
3. Quando houver deploy real (Cloud Run/Cloud Function — ainda não existe para nenhuma camada
   hoje), confirmar a Service Account associada ao job
   (`sa-gcp-billing-hmg@gglobo-billinghomolog-hdg-prd.iam.gserviceaccount.com` em dev,
   `sa-gcp-billing-prd@gglobo-billing-hdg-prd.iam.gserviceaccount.com` em prod, conforme
   `terraform/environments/{dev,prod}/variables.tf`) tem os papéis IAM necessários
   (`roles/bigquery.dataEditor`/`roles/bigquery.jobUser` nos datasets envolvidos, no mínimo).

**Ação corretiva**:
- Local: `gcloud auth application-default login` e `gcloud config set project <projeto>`.
- Service Account de produção/Cloud Run: solicitar ao time de IAM/Plataforma a concessão do
  papel faltante no dataset específico (`billing_raw`, `billing_silver`, `billing_gold`).

**Validação**: rodar novamente a camada/job e confirmar que o erro `403` não se repete.

**Escalonamento**: se a Service Account já deveria ter o papel e mesmo assim falha, escalar para
o time de Plataforma/IAM do projeto GCP correspondente — pode ser propagação de IAM atrasada ou
herança de papel mal configurada a nível de dataset/projeto.

---

## Runbook 4 — Variável de ambiente faltante ou incorreta

**Sintoma**: log `"Please set the environment variable <NOME>"` seguido de
`"Exiting due to missing environment variable(s): ..."`, processo encerra com código 1
imediatamente (`config/base.py:50-55`).

**Diagnóstico**: a mensagem já lista exatamente qual(is) variável(eis) falta(m) — não é preciso
adivinhar. Comparar com `pipelines/<camada>/.env.example` para confirmar a lista completa
esperada por aquela camada.

**Ação corretiva**: exportar a variável faltante no processo que vai rodar o comando (shell
local, ou variável de ambiente do Cloud Run Job/Cloud Function quando o deploy existir).
Atenção a dois erros comuns confirmados pelos `.env.example`:
- Confundir `GCP_SILVER_LABEL_TABLE` (com `_label`, usada pelas camadas Gold Pre-Foundation e
  Silver) com a tabela `gcp_billing_silver` sem `_label` (fora de prioridade de migração,
  conforme `CLAUDE.md`).
- Em `gold_foundation`/`gold`, esquecer que há **duas** tabelas de destino diferentes
  (`GCP_GOLD_LABEL_FOUNDATION_TABLE` vs. `GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE`) — ambas
  obrigatórias.

**Validação**: rodar a camada de novo; o processo deve avançar além da validação de env vars
(não emitir mais o log de "Please set...").

**Escalonamento**: se a variável já está exportada e o erro persiste, verificar se há
diferença de **case** ou espaço em branco no nome da env var, ou se o processo está sendo
executado num shell/contexto diferente de onde a variável foi exportada (problema comum ao
misturar `.env` carregado manualmente com sub-shells).

---

## Runbook 5 — Dados incorretos / divergência de custo

**Sintoma**: validação de paridade bloqueia o load (`status: failed`, `details` com `diff:` alto)
ou, pior, os dados são gravados mas alguém no time financeiro reporta números errados no
dashboard Looker Studio.

**Diagnóstico**:
1. Se bloqueado pela validação: rodar a query `CHECK_*`/`select_*` da camada manualmente no
   BigQuery Console (usar o template em `templates/<camada>_query.py` com os parâmetros reais)
   para visualizar os totais comparados.
2. Se não bloqueado mas o número está errado: a validação de paridade só compara a camada atual
   contra a **imediatamente anterior** no medalhão — um erro introduzido em uma camada anterior
   e replicado consistentemente adiante **não é pego** pela validação (ela compara consistência
   entre camadas adjacentes, não corretude absoluta).
3. Para a camada Unificado especificamente: lembrar do bug de soma com sinal em `diff_total`
   (`unificado_service.py:163-166`) — divergências podem estar se cancelando silenciosamente.
   Recalcular manualmente `dict_column_diff` por provedor/coluna sem somar os sinais.
4. Para `gold`/`gold_foundation`: lembrar dos hardcodes de tabela/projeto de produção
   (`gglobo-billing-hdg-prd`) independentes do `GCP_PROJECT` configurado — se a investigação for
   em homologação, conferir se a divergência não está vindo de dados de produção sendo lidos
   "por engano" via esses hardcodes.

**Ação corretiva**:
- Se a causa for atraso de dados upstream: aguardar e reprocessar (ver `docs/OPERACAO.md` seção
  3).
- Se a causa for um hardcode/bug confirmado (ex.: `2023-12-01` sem o ajuste financeiro): replicar
  o hardcode esperado ou investigar por que ele não foi aplicado (regressão).
- Se a causa for um bug introduzido em camada anterior: reprocessar a partir daquela camada,
  seguindo a ordem do medalhão (Silver → Gold Pre-Foundation → Gold Foundation → Gold →
  Unificado).

**Validação**: comparar manualmente os totais agregados (`SUM(custo)`, `SUM(creditos)` etc.) por
`invoice_month` entre a camada corrigida e a anterior, com tolerância de R$ 0,01 (mesmo padrão
usado no rascunho de reconciliação em
`pipelines/gold_pre_foundation/tests/reconciliation/README.md`).

**Escalonamento**: divergência de custo é sensível financeiramente — escalar para o time de
FinOps/owner do chargeback antes de publicar qualquer correção em produção, especialmente se
afetar `invoice_month` de meses já fechados/reportados.

---

## Runbook 6 — Deploy com erro

**Sintoma**: `terraform apply` falha, ou um recurso provisionado (Cloud Run Job/Cloud Function)
é criado mas toda execução falha.

**Diagnóstico**:
1. Erro de `terraform apply`: ler a mensagem — causas comuns dado o código dos módulos
   reutilizáveis existentes: módulo `secret_manager_secret` espera que
   `accessor_service_account_emails` seja uma lista válida de e-mails de Service Account já
   existentes (o módulo não cria a SA); módulo `bigquery_table` exige que `dataset_id`
   (`billing_raw`) já exista — nenhum ambiente provisiona o dataset via Terraform.
2. Job provisionado mas falha em toda execução: verificar logs do Cloud Run Job/Cloud Function
   e a tag/digest da imagem deployada antes de assumir problema de infraestrutura — confirmar que
   o código que está rodando na imagem corresponde à versão esperada.

**Ação corretiva**:
- Dataset/SA inexistente: provisionar manualmente fora do Terraform (são pré-requisitos, não
  geridos por este módulo) ou ajustar o módulo se o requisito mudar.
- Falha de execução por código desatualizado: garantir que a imagem foi rebuildada/republicada
  após a última correção antes de considerar o componente operacional.

**Validação**: `terraform plan` sem diffs inesperados após `apply`; execução do Cloud Run
Job/Cloud Function correspondente mostrando status `Succeeded`.

**Escalonamento**: para qualquer mudança de Terraform em produção, seguir o processo de
aprovação real do time (⚠️ a confirmar — não documentado neste repositório; ver
`docs/DEPLOYMENT.md`).

---

## Runbook 7 — Problemas de performance

**Sintoma**: execução de uma camada demora visivelmente mais que o histórico, ou custo de
BigQuery (bytes processados) sobe sem mudança de volume de dados de origem.

**Diagnóstico**:
1. Usar a query de custo por `labels` em `docs/TROUBLESHOOTING.md` (seção Monitoramento) para
   comparar `total_bytes_processed` do mesmo `invoice_month`/camada ao longo do tempo.
2. Para a camada Silver: revisar se a janela de partição (`_PARTITION_DAYS_BEFORE = 17`,
   `_PARTITION_DAYS_AFTER = 10`, `silver_label_service.py:42-43`) está maior que o necessário
   para o período sendo processado — ela é fixa, não adaptativa.
3. Para Gold Pre-Foundation/Gold: lembrar que o `SELECT` faz `UNION ALL`/`LEFT JOIN` com várias
   fontes externas fora deste repositório — uma piora de performance nessas fontes (não
   controladas aqui) se propaga diretamente.

**Ação corretiva**: depende da causa raiz identificada — não há tuning de performance
implementado nos templates SQL hoje (são cópias fiéis do legado, sem otimização adicional nesta
migração). Mudanças de performance no SQL são uma decisão deliberada de engenharia (afetam
paridade comportamental) — não fazer ad-hoc.

**Validação**: comparar `total_bytes_processed`/tempo de execução antes/depois da mudança para o
mesmo `invoice_month`.

**Escalonamento**: para qualquer otimização de SQL, envolver o `gcp-data-engineer` e
re-confirmar paridade com o `qa-reconciliation` antes de aplicar em produção — qualquer mudança
de `JOIN`/filtro pode alterar resultado financeiro de forma sutil.
