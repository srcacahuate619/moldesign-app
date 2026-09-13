FROM mambaorg/micromamba:1.5.10 AS base

WORKDIR /app

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
COPY --chown=$MAMBA_USER:$MAMBA_USER requirements.txt /tmp/requirements.txt

RUN micromamba install -y -n base -f /tmp/environment.yml && \
    micromamba clean --all --yes

# --- Install AutoDock Vina 1.2.5 Linux binary ---
ENV VINA_VERSION=1.2.5
ENV VINA_URL=https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v${VINA_VERSION}/vina_${VINA_VERSION}_linux_x86_64
ENV VINA_INSTALL_DIR=/usr/local/bin
ENV VINA_EXECUTABLE_PATH=${VINA_INSTALL_DIR}/vina

# Install wget before downloading Vina (as root), then switch back to micromamba user
USER root
RUN apt-get update -qq && apt-get install -yqq wget openbabel curl && rm -rf /var/lib/apt/lists/* \
    && wget -O /usr/local/bin/vina "$VINA_URL" \
    && chmod +x /usr/local/bin/vina
USER $MAMBA_USER

RUN micromamba run -n base pip install --no-cache-dir -r /tmp/requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN mkdir -p /tmp/vina

COPY --chown=$MAMBA_USER:$MAMBA_USER . /app

FROM base AS development
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
