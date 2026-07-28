ARG PYTHON_IMAGE=python:3.11.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG CODEDISTANCE_REPOSITORY=https://github.com/m-webster/codeDistancePYPI
ARG CODEDISTANCE_COMMIT=a4afe9c09bbf5790da9ecc05b65c5b62343979ad
ARG CODEX_CLI_VERSION=0.144.6

LABEL org.autoqec.baseline="${CODEDISTANCE_COMMIT}"
LABEL org.autoqec.role="proposal"

RUN apt-get update \
    && apt-get install --no-install-recommends -y git ca-certificates build-essential nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin autoqec

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt
RUN git clone "${CODEDISTANCE_REPOSITORY}" /opt/codedistance \
    && git -C /opt/codedistance checkout --detach "${CODEDISTANCE_COMMIT}" \
    && python -m pip install --no-cache-dir /opt/codedistance
RUN npm install --global "@openai/codex@${CODEX_CLI_VERSION}" \
    && npm cache clean --force

USER 10001:10001
WORKDIR /workspace
