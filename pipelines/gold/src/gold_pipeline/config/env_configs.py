"""Configuração de ambiente da camada Gold.

`GoldEnvConfigs` declara as 7 variáveis que `GCPGoldLabelService.__init__`
(legado) de fato lê: ``GCP_PROJECT``, ``CUSTO_UNITARIO_FIELDS``,
``COST_VALIDATION_LIMIT``, ``GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE``,
``GCP_GOLD_LABEL_TABLE``, ``GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE`` e
``GCP_MARKETPLACE_SERVICES_TABLE``.

Nota sobre `CUSTO_UNITARIO_FIELDS`: igual ao achado já documentado em
`pipelines/gold_pre_foundation`, o service legado lê esta env var e expõe
`generate_custom_columns`/`generate_null_columns`, mas nenhum dos dois método
é chamado em `load_gold_data` — código órfão, mantido fielmente.
"""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "CUSTO_UNITARIO_FIELDS",
    "COST_VALIDATION_LIMIT",
    "GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE",
    "GCP_GOLD_LABEL_TABLE",
    "GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE",
    "GCP_MARKETPLACE_SERVICES_TABLE",
]

_DEFAULT_COST_VALIDATION_LIMIT = 15000.0


class GoldEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela camada Gold (`tb_gcp_billing_projeto_ar_label`)."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_bq_table_custo_unitario_fields(self) -> list[str]:
        """Replica o parsing exato do legado: split por vírgula, filtrando vazios."""
        raw_value = self.get("CUSTO_UNITARIO_FIELDS") or ""
        return list(filter(None, raw_value.split(",")))

    def get_cost_validation_limit(self) -> float:
        return float(self.get("COST_VALIDATION_LIMIT", str(_DEFAULT_COST_VALIDATION_LIMIT)))

    def get_gcp_gold_foundation_dashboard_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_FOUNDATION_DASHBOARD_TABLE")

    def get_gcp_gold_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_TABLE")

    def get_gcp_gold_pre_foundation_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE")

    def get_gcp_marketplace_services_table(self) -> str | None:
        return self.get("GCP_MARKETPLACE_SERVICES_TABLE")
