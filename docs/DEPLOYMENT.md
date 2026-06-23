# Deployment — finops-billing

> Lido para escrever este documento: `.gitlab-ci.yml` por completo, todo `terraform/modules/` e
> `terraform/environments/{dev,prod}/`, `pyproject.toml` de cada pacote (para confirmar
> dependências de build). Nenhuma informação sobre processo de aprovação, pipeline de CD real ou
> cutover de produção foi inventada — onde o código não confirma, está marcado explicitamente
> como "a confirmar".

## 1. Estado real hoje (resumo executivo)

| Componente | Terraform real? | Dockerfile real? | CI testa? | Deploy automatizado? |
|---|---|---|---|---|
| `libs/billing_common` | N/A (lib, não deployável isoladamente) | Não | Sim (`pytest-billing-common`) | N/A |
| `pipelines/silver` | **Não** | Não | Sim (`pytest-silver-pipeline`) | **Não** |
| `pipelines/gold_pre_foundation` | **Não** | Não | **Não** (sem job no CI) | **Não** |
| `pipelines/gold_foundation` | **Não** | Não | **Não** (sem job no CI) | **Não** |
| `pipelines/gold` | **Não** | Não | **Não** (sem job no CI) | **Não** |
| `pipelines/unificado` | **Não** | Não | **Não** (sem job no CI) | **Não** |

**Nenhum componente deste repositório tem deploy real hoje.** Existem módulos Terraform
reutilizáveis em `terraform/modules/` (`bigquery_table`, `cloud_run_job`, `cloud_scheduler_http`,
`secret_manager_secret`) e dois métodos de infraestrutura em `libs/billing_common`
(`get_secret_json`, `BigQueryAdapter.insert_rows`), mas **nenhum módulo está instanciado** em
`terraform/environments/{dev,prod}/` e **não há nenhum Dockerfile** no repositório. Esta tabela
é uma confirmação direta do que o `CLAUDE.md` já registrava: "Terraform de deploy (Cloud
Function/Cloud Run + Scheduler) para essas 5 camadas... ainda fora de escopo". Nada mudou nesse
sentido — não há Terraform para nenhuma das 5 camadas do medalhão neste repositório.

## 2. CI — o que existe de fato (`.gitlab-ci.yml`)

```yaml
stages:
  - lint
  - test
```

**Stage `lint`** (roda para todo o workspace, não por pacote):
- `ruff-check`: `uv run ruff check .` + `uv run ruff format --check .` — **bloqueante**.
- `mypy-check`: `uv run mypy libs pipelines` — `allow_failure: true`, **não bloqueia** o
  pipeline (decisão deliberada, documentada no próprio YAML: "trava regressão futura sem travar
  esta entrega por causa de stubs incompletos de libs do GCP").

**Stage `test`** (um job por pacote — **mas só 2 dos 6 pacotes de `pipelines/`+1 de `libs/`
estão cobertos hoje**):
- `pytest-billing-common`: `uv run pytest libs/billing_common/tests -v`.
- `pytest-silver-pipeline`: `uv run pytest pipelines/silver/tests -v`.

**Lacuna confirmada**: não existem jobs `pytest-gold-pre-foundation-pipeline`,
`pytest-gold-foundation-pipeline`, `pytest-gold-pipeline` nem `pytest-unificado-pipeline`. Os
testes desses 4 pacotes existem no repositório e passam localmente, mas **não são executados
automaticamente em nenhum pipeline de CI hoje**. Um bug introduzido em qualquer uma dessas 4
camadas só será detectado por execução manual de `pytest`.

Não há nenhum stage de `deploy` no `.gitlab-ci.yml` — confirmando que não há CD configurado
neste repositório para nenhum componente.

## 3. Terraform — o que existe de fato

### 3.1 Módulos reutilizáveis (`terraform/modules/`)

| Módulo | Recurso provisionado | Usado por |
|---|---|---|
| `bigquery_table` | `google_bigquery_table` com partição por tempo, clustering, `deletion_protection` configurável | Nenhum hoje |
| `cloud_run_job` | `google_cloud_run_v2_job`, com `env_vars` dinâmicos e `lifecycle.ignore_changes` na imagem (permite atualizar a imagem fora do `terraform apply`, ex. via CI/CD de imagem separado) | Nenhum hoje |
| `cloud_scheduler_http` | `google_cloud_scheduler_job` com `http_target` + `oidc_token` (autenticação via Service Account, sem chave de API) | Nenhum hoje |
| `secret_manager_secret` | `google_secret_manager_secret` (container vazio) + `google_secret_manager_secret_iam_member` por SA acessora | Nenhum hoje |

Estes módulos resolvem diretamente o débito técnico nº 3 do `CLAUDE.md` ("Ausência de módulos
Terraform reutilizáveis para recursos repetidos"), mas **nenhum está instanciado** em
`terraform/environments/{dev,prod}/` hoje — existem como infraestrutura reutilizável disponível
para quando as 5 camadas do medalhão ganharem Terraform. O esperado (conforme a "Estrutura alvo"
do `CLAUDE.md`) é que essas camadas reaproveitem `bigquery_table` e `cloud_run_job`/equivalente
de Cloud Function, em vez de criar módulos novos.

### 3.2 Ambientes (`terraform/environments/{dev,prod}/`)

Ambos os ambientes (`dev` e `prod`) hoje só contêm `provider.tf`, `variables.tf` e `outputs.tf`
— nenhum módulo é chamado/instanciado em nenhum dos dois. Isso resolve preventivamente o débito
técnico nº 2 do `CLAUDE.md` ("Terraform assimétrico entre dev e prod"): os dois ambientes
compartilham exatamente a mesma estrutura de arquivos e as mesmas variáveis genéricas, sem
divergência.

| Variável | Dev (`gglobo-billinghomolog-hdg-prd`) | Prod (`gglobo-billing-hdg-prd`) |
|---|---|---|
| `project_id` | `gglobo-billinghomolog-hdg-prd` | `gglobo-billing-hdg-prd` |
| `region` | `us-east1` | `us-east1` |
| `billing_raw_dataset_id` | `billing_raw` (já existente, não gerenciado pelo Terraform) | `billing_raw` |
| `service_account_email` | `sa-gcp-billing-hmg@gglobo-billinghomolog-hdg-prd.iam.gserviceaccount.com` | `sa-gcp-billing-prd@gglobo-billing-hdg-prd.iam.gserviceaccount.com` |

`outputs.tf` de ambos está **vazio hoje**, com um comentário explicando que nenhum módulo está
instanciado ainda — quando o primeiro módulo for chamado (ex.: deploy de uma camada do
medalhão), exportar ali os IDs/URLs úteis (débito técnico nº 6 do `CLAUDE.md`, "`outputs.tf`
vazio").

Backend remoto: `terraform { backend "gcs" {} }` (`provider.tf:14`), sem bucket nomeado no
código — configuração parcial, esperando `-backend-config` no `terraform init` (⚠️ a confirmar
com o time qual bucket/prefixo real é usado em cada ambiente; não está no repositório).

### 3.3 Comandos reais de deploy do Terraform existente

⚠️ **Não há nenhum módulo instanciado em `terraform/environments/{dev,prod}/` hoje** — não
existe comando de `terraform apply` real a documentar para nenhuma camada ainda. O comando
abaixo é o padrão genérico esperado pela estrutura do código, útil apenas quando o primeiro
módulo for instanciado em um dos ambientes:

```bash
cd terraform/environments/dev
terraform init -backend-config="bucket=<BUCKET_A_CONFIRMAR>"
terraform plan
terraform apply
```

⚠️ **A confirmar com o time**: o bucket de backend GCS e o processo de aprovação (quem roda
`terraform apply` em produção, se há revisão obrigatória de `terraform plan` antes).

## 4. Deploy real do legado (referência, não deste repositório)

Conforme `CLAUDE.md`: o legado tem deploy real via Cloud Function `gcp-cost-with-labels` (Gen2),
disparada diariamente via `gcp-workflow-labels-trigger` + Cloud Scheduler, já provisionada em
dev e prod. Esse Terraform/infra **não está neste repositório** — é o alvo a ser substituído
quando as 5 camadas do medalhão ganharem seu próprio Terraform aqui.

## 5. O que falta para as 5 camadas do medalhão terem deploy real (gap conhecido)

Com base na estrutura alvo do `CLAUDE.md` e nos módulos Terraform reutilizáveis já existentes
(`terraform/modules/`, sem consumidor hoje), o trabalho pendente — não feito nesta entrega —
inclui, no mínimo:

1. Decidir o runtime de cada camada (Cloud Function Gen2, como o legado, ou Cloud Run Job —
   ambos os módulos Terraform necessários para qualquer uma das duas opções já existem em
   `terraform/modules/`, prontos para reuso).
2. Criar `terraform/environments/{dev,prod}/<camada>.tf` para cada uma das 5 camadas, reusando
   os módulos `bigquery_table`/`cloud_run_job` (ou um módulo `cloud_function` novo, se a decisão
   do item 1 for usar Cloud Function).
3. Criar `Dockerfile` para cada camada, se o runtime escolhido for Cloud Run.
4. Decidir o agendamento de cada camada — em particular, resolver o achado aberto da camada
   Unificado (ver `docs/ARCHITECTURE.md` seção 8) antes de criar o `cloud_scheduler_http` dela.
5. Adicionar os 4 jobs `pytest-*-pipeline` faltantes no `.gitlab-ci.yml` (`gold-pre-foundation`,
   `gold-foundation`, `gold`, `unificado`).
6. Definir e executar o dual-run/reconciliação real (gate do agente `qa-reconciliation`,
   conforme `CLAUDE.md`) antes de qualquer cutover de produção — hoje só existe o rascunho não
   executável em `pipelines/gold_pre_foundation/tests/reconciliation/README.md`.

## 6. Rollback de deploy (quando houver deploy real)

⚠️ Não aplicável hoje — não há nenhum componente com deploy real neste repositório, logo não há
rollback de deploy a documentar ainda. Quando a primeira camada ganhar Terraform/Cloud Run Job
ou Cloud Function, o padrão recomendado (com base no módulo `cloud_run_job` já existente, que
usa `lifecycle.ignore_changes` na imagem) é:

- Se o módulo seguir o mesmo padrão de `cloud_run_job/main.tf` (`lifecycle.ignore_changes` na
  imagem), o Terraform não controla qual versão da imagem está rodando depois do primeiro
  `apply` — rollback de código seria via `gcloud run jobs update --image=<tag_anterior>`, sem
  reaplicar Terraform.
- Rollback de infraestrutura (Terraform) seria o `terraform apply` de uma revisão anterior do
  `.tf` — ⚠️ a confirmar se haverá tagueamento/versionamento formal de releases de Terraform além
  do histórico do git, quando isso existir.

## 7. Aprovações necessárias

⚠️ **A confirmar com o time** — não há nenhuma definição de `CODEOWNERS`, regra de proteção de
branch, ou etapa de aprovação manual no `.gitlab-ci.yml` deste repositório. Não documentar um
processo de aprovação como se já existisse sem essa confirmação.
