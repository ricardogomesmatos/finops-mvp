"""Configuração de ambiente da camada Gold Foundation.

`GoldFoundationEnvConfigs` declara as 4 variáveis que
`GCPGoldLabelFoundationService.__init__` (legado) de fato lê: ``GCP_PROJECT``,
``GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE`` (tabela de origem, camada anterior do
medalhão), ``GCP_GOLD_LABEL_FOUNDATION_TABLE`` e
``GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE`` (as duas tabelas de destino
desta camada).
"""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE",
    "GCP_GOLD_LABEL_FOUNDATION_TABLE",
    "GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE",
]


class GoldFoundationEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela camada Gold Foundation."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_gcp_gold_pre_foundation_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE")

    def get_gcp_gold_foundation_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_FOUNDATION_TABLE")

    def get_gcp_gold_foundation_dashboard_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE")
