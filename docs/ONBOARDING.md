# Onboarding — finops-billing

> Lido para escrever este documento: todos os `tests/` das 6 pastas de `pipelines/` e de
> `libs/billing_common/tests/` (estrutura de fixtures, padrão de mocks), `pyproject.toml` de cada
> pacote, `.gitlab-ci.yml`, `.pre-commit-config.yaml`. Suíte de testes executada localmente
> (`uv run pytest` via `.venv` do próprio repositório) para confirmar comportamento real antes de
> documentar.

## Para quem está chegando agora

Bem-vindo ao `finops-billing`. Este repositório é a modernização do `gcp-billing` (legado) —
leia `CLAUDE.md` na raiz **antes de qualquer outra coisa**, ele tem o contexto de negócio
completo (o que é chargeback financeiro multicloud, por que existe migração, o que está e o que
não está em escopo).

### Os 3 fatos mais importantes que você precisa internalizar antes de tocar em código

1. **Não existe orquestrador único ainda.** Cada uma das 5 camadas do medalhão
   (`silver`, `gold_pre_foundation`, `gold_foundation`, `gold`, `unificado`) tem seu próprio
   `main.py`, pensado para rodar isoladamente (futura Cloud Function/Cloud Run Job dedicada por
   camada). Se você está procurando um "main.py geral que roda tudo", ele não existe neste
   repositório — só no legado (`gcp_labels/main.py`).
2. **Nenhum componente deste repositório tem deploy automatizado ainda.** Não há Terraform
   instanciado, nem Dockerfile, nem CI de deploy para nenhuma das 5 camadas do medalhão. Existem
   módulos Terraform reutilizáveis (`terraform/modules/`), mas sem nenhuma instância em
   `terraform/environments/{dev,prod}/`. Não assuma que rodar `terraform apply` vai colocar
   Silver/Gold/etc. em produção — isso ainda não foi construído.
3. **Há um achado aberto não resolvido sobre a camada Unificado**: no legado, o fluxo automático
   diário de produção pode não atualizar `tb_gcp_tsuru_dbaas_unificada_labels`. Não assuma que
   essa tabela está sempre atualizada sem checar a data do último `invoice_month` presente nela.

## Principais componentes (mapa rápido)

| Componente | Onde | O que faz |
|---|---|---|
| `libs/billing_common` | `libs/billing_common/src/billing_common/` | Lib compartilhada: `BigQueryAdapter`, `BaseEnvConfigs`, `DateUtil`, `build_logger`, `get_secret_json`. Tudo que um pipeline novo precisa importar em vez de duplicar. |
| 5 camadas do medalhão | `pipelines/{silver,gold_pre_foundation,gold_foundation,gold,unificado}/` | Pipeline de chargeback financeiro multicloud, migrado do legado `gcp_labels`. |
| `terraform/` | `terraform/modules/`, `terraform/environments/{dev,prod}/` | Módulos reutilizáveis (`bigquery_table`, `cloud_run_job`, `cloud_scheduler_http`, `secret_manager_secret`) disponíveis para uso futuro; nenhum módulo está instanciado em `terraform/environments/{dev,prod}/` hoje. |
| `.gitlab-ci.yml` | raiz | CI: lint (Ruff bloqueante, mypy permissivo) + test (só `billing-common` e `silver-pipeline` têm job de teste dedicado hoje). |

## Checklist dos primeiros dias

- [ ] Ler `CLAUDE.md` na raiz (contexto de negócio e de migração).
- [ ] Ler este `docs/ONBOARDING.md` por completo.
- [ ] Ler `docs/ARCHITECTURE.md` e `docs/DATA_FLOW.md` (entender as 5 camadas + o componente
      separado).
- [ ] Clonar/abrir o repositório e rodar `uv sync --all-packages` localmente — ver seção "Como
      validar seu ambiente local" abaixo.
- [ ] Rodar a suíte de testes completa e confirmar que os 101 testes passam no seu ambiente.
- [ ] Ler ao menos um `README.md` de camada por completo (`pipelines/silver/README.md` é o mais
      simples — bom ponto de partida) e correlacionar com o `service`/`template` real.
- [ ] Rodar manualmente a camada Silver contra um projeto de homologação (se já tiver acesso
      GCP configurado) — ver `docs/OPERACAO.md` seção 1-2.
- [ ] Ler `docs/TROUBLESHOOTING.md` e `docs/RUNBOOK.md` por completo — eles documentam achados
      reais de paridade e bugs conhecidos, não cenários hipotéticos.
- [ ] Pedir acesso (ver seção "Como obter acessos" abaixo) antes de tentar rodar qualquer camada
      contra dados reais.

## Como obter acessos

⚠️ **A confirmar com o time** — não há, neste repositório, um processo documentado de concessão
de acesso (é provavelmente gerido por uma ferramenta interna de IAM da Globo, fora do escopo do
código). Pontos que você vai precisar resolver com o time antes de operar este projeto:

- Acesso ao(s) projeto(s) GCP: `gglobo-billinghomolog-hdg-prd` (dev/homologação) e
  `gglobo-billing-hdg-prd` (produção).
- Permissão de leitura nos datasets `billing_raw`, `billing_silver`, `billing_gold` e de
  escrita nas tabelas de destino de cada camada (ver `docs/DATA_FLOW.md` para a lista completa).
- Acesso ao repositório legado `~/gcp-billing` (local: `C:\Users\ricar\gcp-billing`), necessário
  para qualquer trabalho de migração/paridade.
- Acesso ao GitLab do projeto (para CI/CD e revisão de merge requests).

## Como validar seu ambiente local

```bash
cd C:\Users\ricar\OneDrive\Documentos\GitHub\finops-mvp

# 1. Confirmar versão do Python
python --version   # esperado: 3.12.x (ver .python-version)

# 2. Instalar uv, se ainda não tiver
pip install uv

# 3. Sincronizar o workspace inteiro
uv sync --all-packages

# 4. Rodar a suíte completa
uv run pytest

# Resultado esperado: 120 passed
```

Se o passo 4 não mostrar `120 passed`, algo no seu ambiente está diferente do esperado — não
assuma que é falha sua antes de comparar com a saída documentada aqui (validada por execução
real nesta documentação).

Lint e formatação:

```bash
uv run ruff check .
uv run ruff format --check .
```

Type checking (informativo, não bloqueia nada localmente nem no CI):

```bash
uv run mypy libs pipelines
```

## Testes — checklist completo

### Testes unitários

Todas as 5 camadas do medalhão + `billing_common` têm testes unitários que **nunca chamam
BigQuery real** — `BigQueryAdapter` é sempre mockado via `unittest.mock.patch` (padrão visto em
todos os `conftest.py`, ex.: `pipelines/silver/tests/conftest.py:22-28`).

```bash
uv run pytest libs/billing_common/tests -v
uv run pytest pipelines/silver/tests -v
uv run pytest pipelines/gold_pre_foundation/tests -v
uv run pytest pipelines/gold_foundation/tests -v
uv run pytest pipelines/gold/tests -v
uv run pytest pipelines/unificado/tests -v
```

### Testes de "query esperada renderizada do template real"

Padrão usado em todas as 5 camadas (ex.: `pipelines/silver/tests/expected_silver_queries.py`):
o teste não compara contra uma string SQL copiada à mão — ele importa o template Jinja real
(`templates/<camada>_query.py`) e o renderiza com parâmetros de teste fixos, garantindo que a
"query esperada" do teste **nunca diverge do SQL de produção real**. Se você editar um template
SQL, o teste vai capturar a mudança automaticamente (sem precisar atualizar uma string
duplicada à mão).

### Testes de integração / reconciliação (paridade legado vs. novo)

**Não existem testes de integração reais contra BigQuery neste repositório.** O que existe é um
rascunho de queries de reconciliação em
`pipelines/gold_pre_foundation/tests/reconciliation/README.md`, explicitamente marcado como
"NÃO EXECUTÁVEL" — são queries SQL prontas para quando houver um ambiente de dual-run real
(gate do agente `qa-reconciliation`), não testes Python executáveis hoje.

### Testes pós-deploy

⚠️ Não aplicável hoje — nenhuma das 5 camadas do medalhão tem deploy automatizado ainda (sem
Terraform instanciado, sem Dockerfile, sem CI de deploy). Quando o deploy de uma camada existir,
o teste pós-deploy mínimo esperado é: disparar manualmente uma execução do recurso provisionado
(Cloud Run Job/Cloud Function, a depender da decisão de runtime — ver `docs/DEPLOYMENT.md`) e
confirmar uma nova linha na tabela de destino daquela camada com o `invoice_month` esperado.

### Checklist de testes antes de abrir um merge request

- [ ] `uv run pytest <pacote afetado>/tests -v` passando localmente.
- [ ] `uv run ruff check .` e `uv run ruff format --check .` sem erros.
- [ ] Se você alterou um template SQL: confirmar que `tests/expected_*_queries.py` ainda renderiza
      sem erro (ele importa o template real — qualquer erro de sintaxe Jinja aparece aqui).
- [ ] Se você alterou `services/*.py` de uma camada com validação de custo: confirmar que os
      testes de `check_*`/threshold ainda cobrem o comportamento (ver
      `tests/test_*_service.py` da camada).
- [ ] Se você criou um pipeline novo: adicionar um job `pytest-<nome>-pipeline` em
      `.gitlab-ci.yml` (lacuna hoje: só `billing-common` e `silver-pipeline` têm job dedicado).

## FAQ

**Como eu reprocesso um mês específico de uma camada?**
Rode o `main.py` da camada de novo passando o `invoice_month` desejado — todas as camadas fazem
`DELETE` antes do `INSERT`, então é seguro repetir. Ver `docs/OPERACAO.md` seção 3 para exemplos
completos (incluindo backfill de múltiplos meses).

**Como eu rodo só a camada Gold isoladamente, sem rodar as anteriores?**
```bash
uv run python -m gold_pipeline.main 2024-04-01
```
Mas lembre-se: ela lê de `GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE` e
`GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE` — se essas tabelas não tiverem dados para o mesmo
`invoice_month` (porque as camadas anteriores não rodaram para esse mês), a validação de custo
vai falhar ou a query vai retornar vazio.

**Como eu valido se um deploy/execução deu certo?**
Ver `docs/OPERACAO.md` seção 4 — checar o `status` do retorno, contar linhas na tabela de
destino, comparar agregados de custo entre camadas consecutivas, e ler os logs JSON
estruturados (`build_logger`) procurando a linha `"Check result | ..."`.

**Como eu leio os logs de uma execução?**
Localmente, é stdout direto (JSON por linha). Em produção (quando houver deploy), seria via
Cloud Logging — ver filtros prontos em `docs/TROUBLESHOOTING.md` seção Monitoramento. ⚠️ Esses
filtros ainda não foram testados contra um ambiente real, já que não há deploy das 5 camadas —
considerá-los um ponto de partida, não um valor confirmado em produção.

**Como eu atualizo uma variável de ambiente de uma camada?**
Para execução local: editar `.env`/re-exportar no shell. Para um deploy real (quando existir):
seria via Terraform (`env_vars` no módulo `cloud_run_job`, em `terraform/modules/cloud_run_job/`)
— mas isso ainda não está instanciado para nenhuma camada hoje.

**Por que existem `bypass_validation` em alguns serviços e não em outros?**
`SilverLabelService`, `GoldPreFoundationService`, `GoldService` e `UnificadoService` aceitam
`bypass_validation=True` para pular a checagem de paridade de custo. `GoldFoundationService`
também aceita o parâmetro no construtor, mas ele **não tem efeito** — essa camada nunca teve
validação de custo, nem no legado. Não é uma omissão desta migração.

**Por que a camada Unificado não tagueia seus jobs BigQuery com `labels`?**
Porque o legado nunca fez isso para essa camada especificamente (confirmado por leitura) —
preservado fielmente, não é bug introduzido nesta migração. Ver `docs/DATA_FLOW.md`.

**Onde fica o código do legado para eu comparar?**
`C:\Users\ricar\gcp-billing` (local). Sempre leia o código real do legado para confirmar
comportamento — nunca assuma pela documentação do legado nem pela memória de alguém.

**Quem decide o achado aberto sobre a camada Unificado não rodar no fluxo diário?**
Ninguém decidiu ainda — é uma pergunta aberta para o time de negócio/owner do legado. Não tente
"corrigir" isso sozinho agendando a camada por conta própria; ver `CLAUDE.md` e
`docs/ARCHITECTURE.md` seção 8.

**Existe um dashboard ou ferramenta para ver o estado de todas as camadas de uma vez?**
Não, neste repositório. ⚠️ A confirmar com o time se existe algo fora do código (ex.: um painel
interno de monitoramento de Cloud Functions do legado) que possa servir de referência até que
isso seja construído para o novo ambiente.
