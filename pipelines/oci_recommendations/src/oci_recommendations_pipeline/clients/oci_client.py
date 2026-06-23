"""Cliente OCI Optimizer — autenticação via API Key e listagem paginada.

Como o Cloud Run roda no GCP (não em compute OCI), não há Instance Principal
disponível: a autenticação usa API Key (user/tenancy/fingerprint/key_content),
lida do Secret Manager em runtime (ver `billing_common.secrets.secret_manager`).
O dict de config é montado diretamente em memória — sem `oci.config.from_file()`,
que dependeria de um arquivo `~/.oci/config` em disco.
"""

from __future__ import annotations

import oci

_REQUIRED_CONFIG_KEYS = ["user", "fingerprint", "tenancy", "region", "key_content"]


def build_oci_config(secret_payload: dict) -> dict:
    """Monta o dict de config exigido pelo SDK `oci` a partir do secret.

    Espera no secret as chaves: user, fingerprint, tenancy, region, key_content
    (chave privada PEM completa, em memória — nunca um `key_file` em disco).
    """
    missing = [key for key in _REQUIRED_CONFIG_KEYS if not secret_payload.get(key)]
    if missing:
        raise ValueError(f"OCI secret payload missing required key(s): {missing}")

    config = {key: secret_payload[key] for key in _REQUIRED_CONFIG_KEYS}
    oci.config.validate_config(config)
    return config


def build_optimizer_client(secret_payload: dict) -> oci.optimizer.OptimizerClient:
    config = build_oci_config(secret_payload)
    return oci.optimizer.OptimizerClient(config)


def list_all_recommendations(
    optimizer_client: oci.optimizer.OptimizerClient,
    tenancy_id: str,
) -> list:
    """Lista todas as recomendações da tenancy, recursivamente, paginação resolvida.

    Uma única chamada cobre a tenancy inteira via `compartment_id_in_subtree`,
    sem precisar de `IdentityClient`/`list_compartments`.
    """
    response = oci.pagination.list_call_get_all_results(
        optimizer_client.list_recommendations,
        compartment_id=tenancy_id,
        compartment_id_in_subtree=True,
    )
    return response.data
