"""Configuração de ambiente da camada Silver.

No legado, `gcp_labels/utils/env_configs.py` define `EnvConfigs` com 14 variáveis
de ambiente cobrindo as 5 camadas do medalhão (Silver, Gold Pre-Foundation, Gold
Foundation, Gold, Unificado). Como esta entrega migra apenas a camada Silver,
`SilverEnvConfigs` declara somente as 3 variáveis que essa camada de fato lê:
``GCP_PROJECT``, ``GCP_SILVER_LABEL_TABLE`` e ``COST_VALIDATION_LIMIT``.

As demais 11 variáveis do `EnvConfigs` legado pertencem às camadas Gold
Pre-Foundation/Foundation/Gold/Unificado, fora de escopo desta entrega — serão
migradas para suas próprias subclasses de `BaseEnvConfigs` quando essas camadas
forem implementadas.
"""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "GCP_SILVER_LABEL_TABLE",
    "COST_VALIDATION_LIMIT",
]

_DEFAULT_COST_VALIDATION_LIMIT = 15000.0


class SilverEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela camada Silver (`gcp_billing_silver_label`)."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_gcp_silver_label_table(self) -> str | None:
        return self.get("GCP_SILVER_LABEL_TABLE")

    def get_cost_validation_limit(self) -> float:
        return float(self.get("COST_VALIDATION_LIMIT", str(_DEFAULT_COST_VALIDATION_LIMIT)))
