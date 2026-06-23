"""Utilitários de data, compartilhados por todos os pipelines.

Porta `get_first_day_of_this_month`, `get_last_day_of_this_month`, `get_last_month`
e `months_in_range` do legado (`gcp_raw_to_silver/utils/date.py`), com duas
correções deliberadas em relação ao original:

1. **Argumentos nomeados consistentes** (`processing_date=` em todos os métodos) —
   no legado, algumas cópias usavam nomes de parâmetro levemente diferentes entre
   pipelines, dificultando substituição direta.
2. **Sem mutável default em assinatura de função** (`datetime.today()` como
   default seria avaliado uma única vez na importação do módulo, não a cada
   chamada — bug latente do legado). Aqui o default é `None` e o valor "agora" é
   resolvido dentro do corpo do método.

Tipo de retorno: mantém `date` (não `datetime`) para `get_first_day_of_this_month`
e `get_last_day_of_this_month`, igual ao legado. Cuidado ao integrar com código
que espera `datetime` (ex.: `generate_partition_limit_from_invoice_month`, que
usa `datetime.strptime` e portanto precisa de conversão explícita ao chamar
`DateUtil.get_last_day_of_this_month`).
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, timedelta


class DateUtil:
    @staticmethod
    def get_current_month() -> datetime:
        return datetime.today()

    @staticmethod
    def get_first_day_of_this_month(processing_date: date | None = None) -> date:
        processing_date = processing_date or date.today()
        return date(processing_date.year, processing_date.month, 1)

    @staticmethod
    def get_last_day_of_this_month(processing_date: date | None = None) -> date:
        processing_date = processing_date or date.today()
        year = processing_date.year
        month = processing_date.month
        return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)

    @staticmethod
    def get_last_month(processing_date: datetime | None = None) -> datetime:
        processing_date = processing_date or datetime.today()
        return (processing_date.replace(day=1) + timedelta(days=-1)).replace(day=1)

    @staticmethod
    def months_in_range(start_date: str, end_date: str) -> list[str]:
        start, end = (datetime.strptime(value, "%Y-%m-%d") for value in (start_date, end_date))
        return list(
            OrderedDict(
                ((start + timedelta(days=offset)).strftime(r"%Y%m"), None)
                for offset in range((end - start).days)
            ).keys()
        )
