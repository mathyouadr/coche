# Coche - tiny image (~60 MB), no dependency beyond Python itself.
FROM python:3.12-alpine

LABEL org.opencontainers.image.title="Coche" \
      org.opencontainers.image.description="Self-hosted Todoist alternative" \
      org.opencontainers.image.source="https://github.com/mathyouadr/coche" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COCHE_HOST=0.0.0.0 \
    COCHE_PORT=8043 \
    COCHE_DATA_DIR=/data

RUN apk add --no-cache tzdata \
 && adduser -D -H -u 1000 coche \
 && mkdir -p /data \
 && chown coche:coche /data

WORKDIR /app
COPY coche ./coche

USER coche
VOLUME ["/data"]
EXPOSE 8043

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- "http://127.0.0.1:${COCHE_PORT}${COCHE_BASE_PATH}/healthz" >/dev/null || exit 1

ENTRYPOINT ["python", "-m", "coche"]
CMD ["serve"]
