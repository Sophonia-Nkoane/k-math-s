from __future__ import annotations

import os

import uvicorn


if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", os.getenv("APP_PORT", "8000")))
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    reload_enabled = app_env == "development"

    default_workers = "1" if reload_enabled else "2"
    try:
        workers = max(1, int(os.getenv("WEB_CONCURRENCY", default_workers)))
    except ValueError:
        workers = 1 if reload_enabled else 2
    if reload_enabled:
        workers = 1

    log_level = os.getenv("WEB_LOG_LEVEL", "info").strip().lower()
    proxy_headers = os.getenv("WEB_PROXY_HEADERS", "true").strip().lower() in {"1", "true", "yes", "on"}
    forwarded_allow_ips = os.getenv("WEB_FORWARDED_ALLOW_IPS", "*")

    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        reload=reload_enabled,
        workers=workers,
        log_level=log_level,
        proxy_headers=proxy_headers,
        forwarded_allow_ips=forwarded_allow_ips,
        server_header=False,
    )
