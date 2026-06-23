"""Configuração de ambiente da camada Unificado.

`UnificadoEnvConfigs` declara as 3 variáveis que
`GCPUnificadaLabelService.__init__` (legado) de fato lê: ``GCP_PROJECT``,
``GCP_GOLD_UNIFICADO_LABEL_TABLE`` e ``COST_VALIDATION_LIMIT``.
"""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "GCP_GOLD_UNIFICADO_LABEL_TABLE",
    "COST_VALIDATION_LIMIT",
]

_DEFAULT_COST_VALIDATION_LIMIT = 15000.0


class UnificadoEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela camada Unificado (`tb_gcp_tsuru_dbaas_unificada_labels`)."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_gcp_gold_unificado_table(self) -> str | None:
        return self.get("GCP_GOLD_UNIFICADO_LABEL_TABLE")

    def get_cost_validation_limit(self) -> float:
        return float(self.get("COST_VALIDATION_LIMIT", str(_DEFAULT_COST_VALIDATION_LIMIT)))
