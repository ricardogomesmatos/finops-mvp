"""Configuração de ambiente do pipeline de recomendações OCI Optimizer."""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "OCI_RECOMMENDATIONS_TABLE",
    "OCI_TENANCY_ID",
    "OCI_CREDENTIALS_SECRET_ID",
]


class OciRecommendationsEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela extração de recomendações OCI."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_oci_recommendations_table(self) -> str | None:
        return self.get("OCI_RECOMMENDATIONS_TABLE")

    def get_oci_tenancy_id(self) -> str | None:
        return self.get("OCI_TENANCY_ID")

    def get_oci_credentials_secret_id(self) -> str | None:
        return self.get("OCI_CREDENTIALS_SECRET_ID")
