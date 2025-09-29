FROM ghcr.io/astral-sh/uv:debian AS builder

COPY . /project
WORKDIR /project
RUN uv sync --locked
RUN uv run mkdocs build -d public

FROM ghcr.io/static-web-server/static-web-server:2
WORKDIR /
COPY --from=builder /project/public /public

EXPOSE 80
