"""Entry point mínimo da camada Gold Foundation.

Não replica o orquestrador de 5 camadas do `gcp_labels/main.py` (legado) —
fora de escopo desta entrega. Mesmo padrão de
`pipelines/gold_pre_foundation/src/gold_pre_foundation_pipeline/main.py`.
"""

from __future__ import annotations

import sys

from billing_common.dates.date_util import DateUtil
from billing_common.logging.json_logger import build_logger
from gold_foundation_pipeline.services.gold_foundation_service import GoldFoundationService

logger = build_logger(name="gold_foundation_pipeline.main")


def run(invoice_month: str | None = None) -> dict[str, str]:
    """Executa a camada Gold Foundation para o `invoice_month` informado.

    Se `invoice_month` não for informado, usa o primeiro dia do mês corrente
    (mesmo padrão de execução diária do legado).
    """
    if invoice_month is None:
        invoice_month = DateUtil.get_first_day_of_this_month().strftime("%Y-%m-%d")

    logger.info(f"[gold-foundation] Starting gold foundation layer for invoice_month={invoice_month}")
    service = GoldFoundationService()
    result = service.load_gold_foundation_data(invoice_month)
    logger.info(f"[gold-foundation] Finished with status={result['status']}")
    return result


if __name__ == "__main__":
    invoice_month_arg = sys.argv[1] if len(sys.argv) > 1 else None
    outcome = run(invoice_month=invoice_month_arg)
    if outcome["status"] != "success":
        sys.exit(1)
