"""Logger estruturado em JSON, compatível nativamente com Cloud Logging.

Baseado na versão moderna do legado (`gcp_labels/utils/logger.py`), que já havia
abandonado o `LoggingClient` do `google-cloud-logging` em favor de JSON em stdout
(Cloud Logging faz parsing automático de payloads JSON enviados por contêineres/
Cloud Functions). A versão antiga baseada em client de Cloud Logging não foi
portada — é dívida técnica já resolvida no próprio legado.

Diferença em relação ao legado: o logger não é mais um singleton de módulo
(`logger = _build_logger()`); cada pipeline chama `build_logger(name=...)`
explicitamente, permitindo identificar a origem do log (`logger.name`) quando
múltiplos pipelines rodam no mesmo processo (ex.: testes, Cloud Run Job
orquestrando múltiplas camadas).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    """Emite uma linha JSON por registro de log.

    Cloud Logging lê o campo ``severity`` automaticamente, então filtrar por
    ``severity >= INFO`` no Cloud Logging esconde linhas DEFAULT sem precisar
    de configuração adicional no lado do GCP.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "logger": record.name,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def build_logger(name: str = "billing-pipeline", level: int = logging.INFO) -> logging.Logger:
    """Cria (ou recupera) um logger configurado com saída JSON em stdout.

    Idempotente em relação a handlers duplicados: se o logger já tiver um
    handler registrado (ex.: chamado duas vezes no mesmo processo/teste), não
    adiciona um segundo — evita linhas de log duplicadas.
    """
    log = logging.getLogger(name)
    log.setLevel(level)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        log.addHandler(handler)
        log.propagate = False
    return log
