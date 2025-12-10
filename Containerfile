# A container for Woodpecker CI
# This it NOT meant to be used in any other context
FROM debian:trixie-slim AS ci

ENV UV_LINK_MODE=copy
ENV PATH=.venv/bin:$PATH

RUN apt update && apt install cargo gpg git -y

COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

# install different python versions and populate the pypi cache,
# this way woodpecker does not have to make network calls unless
# we change the dependencies

COPY pyproject.toml uv.lock .

RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
        uv python pin $VER ; \
        uv sync --frozen --all-groups --no-install-project ; \
	done

# Containers used to build wheels
FROM quay.io/pypa/musllinux_1_2_x86_64 AS musllinux-amd64
# preinstall python versions to avoid requiring to fetch them in CI
RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
	done
RUN apk add cargo
RUN mkdir /io
WORKDIR /io

FROM quay.io/pypa/musllinux_1_2_aarch64 AS musllinux-arm64
# for some reason, the old uv of this specific container cannot install python > 3.13
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN mv /root/.local/bin/uv /usr/local/bin/
RUN apk add cargo
# preinstall python versions to avoid requiring to fetch them in CI
RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
	done
RUN mkdir /io
WORKDIR /io

FROM quay.io/pypa/manylinux2014_x86_64 AS manylinux-amd64
# preinstall python versions to avoid requiring to fetch them in CI
RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
	done
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN mkdir /io
WORKDIR /io

FROM quay.io/pypa/manylinux2014_aarch64 AS manylinux-arm64
# preinstall python versions to avoid requiring to fetch them in CI
RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
	done
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y
ENV PATH="/root/.cargo/bin:$PATH"
RUN mkdir /io
WORKDIR /io
