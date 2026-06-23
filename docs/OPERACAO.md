# Guia operacional — finops-billing

> Lido para escrever este documento: `main.py`, `services/*.py`, `config/env_configs.py` e
> `.env.example` das 5 pastas em `pipelines/`, `pyproject.toml` de cada pacote,
> `.gitlab-ci.yml`. Todos os comandos abaixo foram conferidos contra o código real (assinatura
> de função, nome de variável de ambiente, caminho de módulo) — nenhum é hipotético. Comandos de
> teste/lint foram executados localmente para confirmar que funcionam neste repositório.

## 1. Como rodar localmente — passo a passo completo

### 1.1 Instalar dependências

```bash
cd C:\Users\ricar\OneDrive\Documentos\GitHub\finops-mvp
uv sync --all-packages
```

Isso resolve `libs/billing_common` e todas as 5 pastas de `pipelines/*` em um único `.venv` na
raiz, usando o `uv.lock` versionado.

### 1.2 Configurar variáveis de ambiente de uma camada

Cada camada tem seu próprio `.env.example`. Nenhuma variável tem valor default embutido no
código além de `COST_VALIDATION_LIMIT` (default `15000.0`, usado só se a env var existir mas
estiver vazia — se a env var **não existir**, `BaseEnvConfigs.validate()` chama `sys.exit(1)`
antes de qualquer lógica de negócio rodar).

Exemplo real para a camada Silver:

```bash
cd pipelines/silver
cp .env.example .env
```

Edite `.env` com os valores do ambiente desejado. Para rodar contra **homologação** (valores já
presentes no `.env.example`):

```env
GCP_PROJECT=gglobo-billinghomolog-hdg-prd
GCP_SILVER_LABEL_TABLE=gglobo-billinghomolog-hdg-prd.billing_silver.gcp_billing_silver_label
COST_VALIDATION_LIMIT=15000
```

> ⚠️ O código não carrega `.env` automaticamente (não há `python-dotenv` em nenhum
> `pyproject.toml` do workspace, confirmado por leitura). É preciso exportar as variáveis no
> shell antes de rodar, ou usar uma ferramenta externa como `dotenv run` / `direnv`. No
> PowerShell, exporte assim:
> ```powershell
> Get-Content .env | ForEach-Object {
>   if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
>     [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim())
>   }
> }
> ```
> No bash:
> ```bash
> set -a && source .env && set +a
> ```

### 1.3 Autenticação GCP (necessária só para rodar contra BigQuery real)

`BigQueryAdapter` usa `google.cloud.bigquery.Client(project=project_id, client_options=...)`
sem credenciais explícitas no código — depende das Application Default Credentials (ADC) do
ambiente:

```bash
gcloud auth application-default login
gcloud config set project gglobo-billinghomolog-hdg-prd
```

⚠️ **A confirmar com o time**: qual Service Account/perfil de IAM é esperado para rodar cada
camada localmente (leitura de `billing_raw`/`billing_gold` e escrita nas tabelas de destino).
Não há nenhuma referência a Service Account de desenvolvedor neste repositório — apenas as SAs
de execução do Terraform (`sa-gcp-billing-hmg@...`/`sa-gcp-billing-prd@...`), que são para os
Cloud Run Jobs, não para uso interativo.

## 2. Executar cada camada manualmente

Todas as 5 camadas do medalhão seguem o mesmo padrão de CLI: `uv run python -m
<nome>_pipeline.main [invoice_month]`. Se `invoice_month` for omitido, o `main.py` usa
`DateUtil.get_first_day_of_this_month()` (primeiro dia do mês corrente) — mesmo padrão do
legado.

### Silver

```bash
uv run python -m silver_pipeline.main 2024-04-01
```

Equivalente programático (útil para depuração interativa ou notebooks):

```python
from silver_pipeline.services.silver_label_service import SilverLabelService

service = SilverLabelService(bypass_validation=False)
result = service.load_silver_data(invoice_month="2024-04-01")
print(result)  # {"status": "success"|"failed", "details": "..."}
```

### Gold Pre-Foundation

```bash
uv run python -m gold_pre_foundation_pipeline.main 2024-04-01
```

```python
from gold_pre_foundation_pipeline.services.gold_pre_foundation_service import (
    GoldPreFoundationService,
)

service = GoldPreFoundationService(bypass_validation=False)
result = service.load_gold_pre_foundation_data(invoice_month="2024-04-01")
```

### Gold Foundation

```bash
uv run python -m gold_foundation_pipeline.main 2024-04-01
```

```python
from gold_foundation_pipeline.services.gold_foundation_service import GoldFoundationService

service = GoldFoundationService()
result = service.load_gold_foundation_data(invoice_month="2024-04-01")
```

> Esta camada não aceita `bypass_validation` de forma útil — o parâmetro existe no construtor
> mas não tem efeito (não há validação de custo nesta camada).

### Gold

```bash
uv run python -m gold_pipeline.main 2024-04-01
```

```python
from gold_pipeline.services.gold_service import GoldService

service = GoldService(bypass_validation=False)
result = service.load_gold_data(invoice_month="2024-04-01")
```

> ⚠️ Esta camada sempre executa `backup_rateio_bq_valiant()` ao final, escrevendo em
> `gglobo-billing-hdg-prd.billing_gold.backup_rateio_bq_slots_fora_org` (tabela hardcoded de
> produção) — mesmo rodando localmente contra homologação. Não há flag para desabilitar esse
> efeito colateral. Considere isso antes de rodar repetidamente em testes manuais.

### Unificado

```bash
uv run python -m unificado_pipeline.main 2024-04-01
```

```python
from unificado_pipeline.services.unificado_service import UnificadoService

service = UnificadoService(bypass_validation=False)
result = service.load_gold_unificado_data(invoice_month="2024-04-01")
```

> ⚠️ Ver achado aberto sobre o agendamento desta camada (`docs/ARCHITECTURE.md`, seção 8) antes
> de assumir que ela já roda automaticamente em algum ambiente.

## 3. Como reprocessar um período (reprocessamento manual)

Todas as 5 camadas do medalhão são idempotentes por `invoice_month` — fazem `DELETE WHERE
invoice_month = '<mes>'` antes do `INSERT`. Reprocessar é simplesmente rodar a camada de novo
para o mesmo mês:

```bash
# Reprocessar abril/2024 na camada Silver
uv run python -m silver_pipeline.main 2024-04-01
```

**Reprocessar a cadeia completa de um mês** (sem orquestrador único — rodar camada por camada,
em ordem, manualmente):

```bash
uv run python -m silver_pipeline.main 2024-04-01 && \
uv run python -m gold_pre_foundation_pipeline.main 2024-04-01 && \
uv run python -m gold_foundation_pipeline.main 2024-04-01 && \
uv run python -m gold_pipeline.main 2024-04-01 && \
uv run python -m unificado_pipeline.main 2024-04-01
```

> O `&&` garante que uma camada só roda se a anterior saiu com código 0 (sucesso) — todos os
> `main.py` chamam `sys.exit(1)` quando `status != "success"` (confirmado em cada `main.py`,
> linha final). Se uma camada falhar, a cadeia para automaticamente.

**Reprocessar vários meses em sequência** (ex.: backfill de um trimestre):

```bash
for mes in 2024-01-01 2024-02-01 2024-03-01; do
  echo "Reprocessando $mes..."
  uv run python -m silver_pipeline.main "$mes" || { echo "FALHOU em $mes"; break; }
done
```

**Bypass de validação de custo** (use com cautela — pula a checagem de paridade, útil para
backfill histórico onde se sabe que o delta é esperado, ex.: mês com hardcode de correção):

```python
from silver_pipeline.services.silver_label_service import SilverLabelService

service = SilverLabelService(bypass_validation=True)
result = service.load_silver_data(invoice_month="2023-12-01")
```

> ⚠️ `GoldFoundationService` não tem parâmetro de bypass útil (não tem validação). Para as
> demais (Silver, Gold Pre-Foundation, Gold, Unificado), `bypass_validation=True` pula
> integralmente o `check_*`/`check_result_query` — não há bypass parcial.

## 4. Como validar o resultado de uma execução

### 4.1 Pelo retorno do `main.py`/service

```python
result = service.load_silver_data(invoice_month="2024-04-01")
# {"status": "success", "details": ""}                      -> OK, sem divergência relevante
# {"status": "success", "details": "invoice_month: ..., diff: 1234.56, ..."} -> OK, mas com
#                                                                                divergência entre
#                                                                                0.01 e o limite
# {"status": "failed", "details": "invoice_month: ..., diff: 99999.99, ..."} -> bloqueado, diff
#                                                                                excedeu o limite
```

Em shell, o código de saída do processo reflete o status:

```bash
uv run python -m silver_pipeline.main 2024-04-01
echo "exit code: $?"   # 0 = success, 1 = failed
```

### 4.2 Validar diretamente no BigQuery

Contar linhas gravadas no período:

```sql
SELECT COUNT(*) AS qtd_linhas
FROM `gglobo-billinghomolog-hdg-prd.billing_silver.gcp_billing_silver_label`
WHERE invoice_month = '2024-04-01'
```

Comparar custo agregado entre camadas consecutivas (mesmo princípio usado em
`pipelines/gold_pre_foundation/tests/reconciliation/README.md`):

```sql
SELECT
  SUM(custo) AS custo_total,
  SUM(creditos) AS creditos_total
FROM `gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
WHERE invoice_month = '2024-04-01'
```

### 4.3 Validar pelos logs estruturados

Todo log de execução sai em JSON no stdout (`build_logger`), por exemplo:

```json
{"severity": "INFO", "message": "[silver] Check result | custo_silver=123456.7800 credito_silver=-200.0000 total_silver=123256.7800 | custo_raw=123256.7600 credito_raw=0.0000 total_raw=123256.7600 | delta=0.0200 limit=15000.0", "timestamp": "2026-06-23T10:00:00+00:00", "logger": "silver_pipeline.silver_label_service"}
```

Cada camada loga a linha `[<camada>] Check result | ...` (exceto Gold Foundation, que não tem
checagem) antes de decidir bloquear ou seguir — é a forma mais rápida de confirmar visualmente
se uma divergência está dentro do esperado.

## 5. Como acompanhar uma execução em andamento

Localmente: a saída é síncrona no terminal (stdout), já que `exec_query` chama
`job.result(timeout=None)` — o processo bloqueia até o job do BigQuery terminar
(`bigquery.py:61`). Não há streaming de progresso parcial; o log mostra "BQ job submitted" e só
depois "BQ job completed" quando o job realmente finalizar.

Em produção (quando houver deploy — ver `docs/DEPLOYMENT.md`), o acompanhamento seria via Cloud
Logging, filtrando pelo `logger` (nome do módulo) e `severity`. Ver `docs/TROUBLESHOOTING.md`
seção de monitoramento para os filtros exatos.

## 6. Como cancelar uma execução em andamento

Localmente: `Ctrl+C` no terminal interrompe o processo Python, mas **não cancela o job no
BigQuery** — `BigQueryAdapter.exec_query` não captura `KeyboardInterrupt` para chamar
`job.cancel()`. O job pode continuar rodando no BigQuery (e gerando custo) mesmo após o processo
local ser interrompido. Para cancelar de fato:

```bash
# Listar jobs em execução, filtrando pelo label de FinOps tagging usado pelas camadas
bq ls -j --min_creation_time=$(date -u -d '10 minutes ago' +%s)000 --project_id=gglobo-billinghomolog-hdg-prd
bq cancel <job_id>
```

Ou via Console BigQuery: `Job History` → localizar pelo `job_id` logado em "BQ job submitted:
<job_id>" → Cancel.

## 7. Como fazer rollback de uma camada

Não existe rollback automático — não há transação BigQuery cobrindo `DELETE` + `INSERT` como uma
unidade atômica (são duas chamadas `exec_query` separadas). Rollback manual:

```sql
-- 1. Confirmar o que existia antes (se houver backup/snapshot anterior, ex. tabela de staging
--    ou export). Se não houver, este passo é o ponto de atenção: sem backup explícito, o
--    DELETE é destrutivo e o rollback depende de reprocessar a partir da camada anterior.

-- 2. Apagar os dados problemáticos do período
DELETE FROM `gglobo-billinghomolog-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
WHERE invoice_month = '2024-04-01';

-- 3. Reprocessar a camada com os dados de origem corretos
```

```bash
uv run python -m gold_pre_foundation_pipeline.main 2024-04-01
```

**Estratégia recomendada de rollback seguro** (⚠️ a confirmar com o time se já existe prática
formal): antes de reprocessar um período em produção, exportar a tabela de destino daquele
`invoice_month` para uma tabela de backup nomeada com timestamp:

```sql
CREATE TABLE `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation_backup_20260623`
AS SELECT * FROM `gglobo-billing-hdg-prd.billing_gold.tb_gcp_gold_pre_foundation`
WHERE invoice_month = '2024-04-01';
```

## 8. Como fazer deploy

Ver `docs/DEPLOYMENT.md` para o processo completo. Resumo operacional: nenhuma das 5 camadas do
medalhão tem Dockerfile, Terraform instanciado ou processo de deploy automatizado neste
repositório hoje — rodar localmente (`uv run python -m <camada>_pipeline.main`) é a única forma
de execução disponível até que o Terraform/Cloud Function dessas camadas seja criado.

## 9. Checklist rápido antes de qualquer execução manual em produção

- [ ] Confirmar `GCP_PROJECT` apontando para o projeto correto (`gglobo-billing-hdg-prd` para
      produção, `gglobo-billinghomolog-hdg-prd` para homologação) — **nunca rodar contra
      produção sem confirmação explícita**, especialmente camadas com tabelas hardcoded de
      produção (`gold`, `gold_foundation`).
  - [ ] Se a camada for `gold`, lembrar que `backup_rateio_bq_valiant()` e o `MERGE` de
      lançamentos Looker **sempre leem/escrevem em `gglobo-billing-hdg-prd`**, mesmo que
      `GCP_PROJECT` aponte para homologação.
- [ ] Confirmar `invoice_month` no formato exato `YYYY-MM-DD` (primeiro dia do mês) — um formato
      diferente faz `datetime.strptime` levantar exceção, capturada e retornada como
      `status="failed"`.
- [ ] Ter um plano de rollback (backup do período antes do reprocessamento) se a execução for em
      produção.
- [ ] Verificar se a camada anterior do medalhão já rodou com sucesso para o mesmo
      `invoice_month` (não há checagem automática de dependência entre camadas — é
      responsabilidade de quem executa, já que não existe orquestrador).
