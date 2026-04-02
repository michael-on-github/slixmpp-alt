# A container for Woodpecker CI
# This it NOT meant to be used in any other context
FROM debian:trixie-slim AS ci

ENV UV_LINK_MODE=copy
ENV PATH=.venv/bin:$PATH

RUN echo "Types: deb deb-src\nURIs: http://deb.debian.org/debian\nSuites: trixie-backports\nComponents: main\nEnabled: yes\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg" \
    > /etc/apt/sources.list.d/debian-backports.sources
RUN apt update && \
    apt install \
        rustc/trixie-backports \
        cargo/trixie-backports \
        gpg \
        git -y && \
    rm -rf /var/lib/apt/lists/*

COPY ./itests/prosody.crt /usr/local/share/ca-certificates/
RUN update-ca-certificates
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

# install different python versions and populate the pypi cache,
# this way woodpecker does not have to make network calls unless
# we change the dependencies

COPY pyproject.toml uv.lock .

RUN for VER in 3.11 3.12 3.13 3.14; do \
        uv python install $VER ; \
        uv python pin $VER ; \
        uv sync --frozen --only-group lint --no-install-project ; \
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

# Prosody server for integration tests
FROM docker.io/library/alpine:edge as prosody
RUN apk add prosody luarocks openssl
RUN ln -s /usr/bin/luarocks-?.? /usr/bin/luarocks  # luarocks is apparently not packaged correctly in alpine?
COPY ./itests/prosody.cfg.lua /etc/prosody/prosody.cfg.lua
COPY ./itests/prosody.crt ./itests/prosody.key /etc/prosody/certs/
RUN mkdir /var/www && echo "null" > /var/www/status.json
RUN prosodyctl register slix-ci-1 prosody slix-ci-1-pass
RUN prosodyctl register slix-ci-2 prosody slix-ci-2-pass
RUN prosodyctl install --server=https://modules.prosody.im/rocks/ mod_muc_moderation
RUN prosodyctl install --server=https://modules.prosody.im/rocks/ mod_service_outage_status
USER prosody
ENTRYPOINT ["prosody", "-F"]
