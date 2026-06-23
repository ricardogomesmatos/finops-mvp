"""Entry point mínimo da camada Silver.

Não replica o orquestrador de 5 camadas do `gcp_labels/main.py` (legado) — fora
de escopo desta entrega, que migra apenas a camada Silver. Pensado para ser
invocado por um Cloud Function/Cloud Run Job dedicado a esta camada, recebendo
`invoice_month` via payload da requisição/evento.
"""

from __future__ import annotations

import sys

from billing_common.dates.date_util import DateUtil
from billing_common.logging.json_logger import build_logger
from silver_pipeline.services.silver_label_service import SilverLabelService

logger = build_logger(name="silver_pipeline.main")


def run(invoice_month: str | None = None, bypass_validation: bool = False) -> dict[str, str]:
    """Executa a camada Silver para o `invoice_month` informado.

    Se `invoice_month` não for informado, usa o primeiro dia do mês corrente
    (mesmo padrão de execução diária do legado).
    """
    if invoice_month is None:
        invoice_month = DateUtil.get_first_day_of_this_month().strftime("%Y-%m-%d")

    logger.info(f"[silver] Starting silver layer for invoice_month={invoice_month}")
    service = SilverLabelService(bypass_validation=bypass_validation)
    result = service.load_silver_data(invoice_month)
    logger.info(f"[silver] Finished with status={result['status']}")
    return result


if __name__ == "__main__":
    invoice_month_arg = sys.argv[1] if len(sys.argv) > 1 else None
    outcome = run(invoice_month=invoice_month_arg)
    if outcome["status"] != "success":
        sys.exit(1)
