"""billing_common — biblioteca interna compartilhada por todos os pipelines do finops-billing.

Centraliza utilitários antes duplicados entre Cloud Functions do ambiente legado
(`gcp-billing`): adapter de BigQuery, logger estruturado, configuração de variáveis
de ambiente e utilitários de data. Nunca duplique estes módulos em um pipeline —
importe daqui.
"""

__version__ = "0.1.0"
