"""silver_pipeline — camada Silver do medalhão moderno (gcp_labels), primeira de 5.

Aplica labels de negócio (squad/produto) sobre o billing raw do GCP e grava o
resultado em `billing_silver`, com validação de paridade de custo (raw vs silver)
antes do load. Migrado de `gcp_labels` (legado), mantendo paridade funcional e
importando utilitários comuns de `billing_common` em vez de duplicá-los.
"""
