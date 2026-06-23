"""Leitura de segredos no Secret Manager, compartilhada por todos os pipelines.

Centraliza o acesso a credenciais lidas em runtime, sem depender de arquivo em
disco — necessário para pipelines que rodam em Cloud Run/Cloud Functions e
precisam autenticar contra serviços externos.
"""

from __future__ import annotations

import json

from google.cloud import secretmanager


def get_secret_json(project_id: str, secret_id: str, version: str = "latest") -> dict:
    """Lê uma versão de segredo e desserializa o payload como JSON.

    Args:
        project_id: projeto GCP onde o segredo está armazenado.
        secret_id: nome do segredo (sem o prefixo `projects/.../secrets/`).
        version: versão do segredo a ler (default: `latest`).

    Returns:
        O payload do segredo desserializado como dict.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    try:
        response = client.access_secret_version(name=name)
    except Exception as exc:
        raise RuntimeError(f"Failed to access secret {secret_id}: {exc}") from exc
    return json.loads(response.payload.data.decode("utf-8"))
