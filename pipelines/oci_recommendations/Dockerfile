# Build context deve ser a raiz do repositório (necessário para alcançar
# libs/billing_common via uv workspace):
#   docker build -f pipelines/oci_recommendations/Dockerfile -t oci-recommendations-runner .
#
# Deployado como Cloud Run Job (sem servidor HTTP) — executa main.py até o
# fim e encerra. Mesmo padrão do fullyear-runner do legado, adaptado para uv
# workspace em vez de requirements.txt solto.

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY libs/billing_common ./libs/billing_common
COPY pipelines/oci_recommendations ./pipelines/oci_recommendations

RUN pip install --no-cache-dir uv && \
    uv pip install --system ./libs/billing_common ./pipelines/oci_recommendations

WORKDIR /app/pipelines/oci_recommendations

CMD ["python", "-m", "oci_recommendations_pipeline.main"]
