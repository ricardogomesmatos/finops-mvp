"""Entry point mínimo da camada Unificado.

Não replica o orquestrador de 5 camadas do `gcp_labels/main.py` (legado) —
fora de escopo desta entrega. Mesmo padrão de
`pipelines/gold_pre_foundation/src/gold_pre_foundation_pipeline/main.py`.

Achado importante documentado em `CLAUDE.md` da raiz do repositório: o branch
`pre_dbaas_tsuru` do orquestrador legado (modo padrão de produção) **não**
chama esta camada — confirmar com o usuário se este pipeline deve ser
agendado de forma independente ou se é um bug do legado a corrigir.
"""

from __future__ import annotations

import sys

from billing_common.dates.date_util import DateUtil
from billing_common.logging.json_logger import build_logger
from unificado_pipeline.services.unificado_service import UnificadoService

logger = build_logger(name="unificado_pipeline.main")


def run(invoice_month: str | None = None, bypass_validation: bool = False) -> dict[str, object]:
    """Executa a camada Unificado para o `invoice_month` informado.

    Se `invoice_month` não for informado, usa o primeiro dia do mês corrente
    (mesmo padrão de execução diária do legado).
    """
    if invoice_month is None:
        invoice_month = DateUtil.get_first_day_of_this_month().strftime("%Y-%m-%d")

    logger.info(f"[gold-unificado] Starting unificado layer for invoice_month={invoice_month}")
    service = UnificadoService(bypass_validation=bypass_validation)
    result = service.load_gold_unificado_data(invoice_month)
    logger.info(f"[gold-unificado] Finished with status={result['status']}")
    return result


if __name__ == "__main__":
    invoice_month_arg = sys.argv[1] if len(sys.argv) > 1 else None
    outcome = run(invoice_month=invoice_month_arg)
    if outcome["status"] != "success":
        sys.exit(1)
