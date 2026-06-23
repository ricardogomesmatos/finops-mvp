"""Configuração de ambiente da camada Gold Pre-Foundation.

No legado, `gcp_labels/utils/env_configs.py` define `EnvConfigs` com 14
variáveis de ambiente cobrindo as 5 camadas do medalhão (Silver, Gold
Pre-Foundation, Gold Foundation, Gold, Unificado). Como esta entrega migra
apenas a camada Gold Pre-Foundation, `GoldPreFoundationEnvConfigs` declara
somente as 6 variáveis que `GCPGoldLabelPreFoundationService.__init__` de
fato lê: ``GCP_PROJECT``, ``GCP_SILVER_LABEL_TABLE`` (a Silver COM labels,
``gcp_billing_silver_label`` — não a ``gcp_billing_silver`` sem label),
``GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE``, ``CUSTO_UNITARIO_FIELDS``,
``GCP_MARKETPLACE_SERVICES_TABLE`` e ``COST_VALIDATION_LIMIT``.

As demais variáveis do `EnvConfigs` legado pertencem às camadas Gold
Foundation/Gold/Unificado, fora de escopo desta entrega — serão migradas
para suas próprias subclasses de `BaseEnvConfigs` quando essas camadas forem
implementadas.

Nota sobre `CUSTO_UNITARIO_FIELDS`: confirmado por leitura do template SQL
real (`templates/gold_pre_foundation_query.py`) que os parâmetros Jinja
derivados desta env var (`custo_unitario_column_names`/`generate_null_columns`,
montados pelo service) não são referenciados em nenhuma das 4 queries da
camada — aparentam ser código órfão no legado. A variável é mantida aqui
fielmente (paridade comportamental), não removida. Ver docstring do template
e relatório de migração para detalhe.
"""

from __future__ import annotations

from billing_common.config.base import BaseEnvConfigs

_EXPECTED_ENVS = [
    "GCP_PROJECT",
    "GCP_SILVER_LABEL_TABLE",
    "GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE",
    "CUSTO_UNITARIO_FIELDS",
    "GCP_MARKETPLACE_SERVICES_TABLE",
    "COST_VALIDATION_LIMIT",
]

_DEFAULT_COST_VALIDATION_LIMIT = 15000.0


class GoldPreFoundationEnvConfigs(BaseEnvConfigs):
    """Variáveis de ambiente exigidas pela camada Gold Pre-Foundation (`tb_gcp_gold_pre_foundation`)."""

    def __init__(self, environ: dict[str, str] | None = None) -> None:
        super().__init__(expected_envs=_EXPECTED_ENVS, environ=environ)

    def get_project_id(self) -> str | None:
        return self.get("GCP_PROJECT")

    def get_gcp_silver_label_table(self) -> str | None:
        return self.get("GCP_SILVER_LABEL_TABLE")

    def get_gcp_gold_pre_foundation_table(self) -> str | None:
        return self.get("GCP_GOLD_LABEL_PRE_FOUNDATION_TABLE")

    def get_bq_table_custo_unitario_fields(self) -> list[str]:
        """Replica o parsing exato do legado: split por vírgula, filtrando vazios.

        Não aplica `.strip()` por item aqui (igual ao legado) — o `.strip()`
        ocorre no consumo, dentro de `generate_custom_columns`/
        `generate_null_columns` do service.
        """
        raw_value = self.get("CUSTO_UNITARIO_FIELDS") or ""
        return list(filter(None, raw_value.split(",")))

    def get_gcp_marketplace_services_table(self) -> str | None:
        return self.get("GCP_MARKETPLACE_SERVICES_TABLE")

    def get_cost_validation_limit(self) -> float:
        return float(self.get("COST_VALIDATION_LIMIT", str(_DEFAULT_COST_VALIDATION_LIMIT)))
