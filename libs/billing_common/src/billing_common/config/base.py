"""Configuração base de variáveis de ambiente, compartilhada por todos os pipelines.

No legado, cada Cloud Function mantinha sua própria classe `EnvConfigs` com um
`validate()` quase idêntico, mas com a lista de `expected_envs` hardcoded dentro
da própria classe (ex.: `gcp_labels/utils/env_configs.py` tem 14 variáveis cobrindo
as 5 camadas; `gcp_raw_to_silver/utils/env_configs.py` tem outras 5 variáveis
totalmente diferentes). Isso forçava duplicar a classe inteira a cada pipeline.

`BaseEnvConfigs` resolve isso recebendo `expected_envs` no construtor: cada
pipeline cria uma subclasse fina com sua própria lista de variáveis e getters
tipados, sem duplicar a lógica de validação.
"""

from __future__ import annotations

import os
import sys

from billing_common.logging.json_logger import build_logger

logger = build_logger(name="billing_common.config")


class BaseEnvConfigs:
    """Valida e expõe acesso a variáveis de ambiente obrigatórias de um pipeline.

    Args:
        expected_envs: lista de nomes de variáveis de ambiente que devem estar
            presentes no processo. Cada pipeline define a sua própria lista.
        environ: fonte de variáveis de ambiente; injetável para testes
            (default: ``os.environ``).
    """

    def __init__(
        self,
        expected_envs: list[str],
        environ: dict[str, str] | None = None,
    ) -> None:
        self.expected_envs = expected_envs
        self.environment_configs = environ if environ is not None else os.environ
        self.validate()

    def validate(self) -> None:
        """Garante que todas as variáveis obrigatórias estão definidas.

        Mantém o comportamento do legado: encerra o processo (`sys.exit(1)`)
        em caso de variável faltante, em vez de levantar exceção silenciosa em
        produção — falha rápido e visível no log do Cloud Function/Cloud Run.
        """
        missing = [env for env in self.expected_envs if env not in self.environment_configs]
        if missing:
            for env in missing:
                logger.error("Please set the environment variable %s", env)
            logger.error("Exiting due to missing environment variable(s): %s", ", ".join(missing))
            sys.exit(1)

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.environment_configs.get(key, default)
