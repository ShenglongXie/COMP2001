from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__", "main"]


def main() -> None:
    import uvicorn

    from _2001.core.config import Settings
    from _2001.core.logging import configure_logging

    settings = Settings.from_env()
    configure_logging(settings)
    uvicorn.run(
        "_2001.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )
