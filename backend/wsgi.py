"""Waitress entry point. Caddy terminates TLS and proxies to 127.0.0.1."""
from waitress import serve

from app import create_app

app = create_app()

if __name__ == "__main__":
    serve(
        app,
        host="127.0.0.1",
        port=app.config["AVIRAT"].port,
        threads=8,
        trusted_proxy="127.0.0.1",
        trusted_proxy_headers={"x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"},
        clear_untrusted_proxy_headers=True,
    )
