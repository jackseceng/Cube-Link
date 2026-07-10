"""Configuration module for Gunicorn, used from: https://dev.to/lionelmarco/how-to-add-flask-gunicorn-packages-to-a-distroless-docker-container-2ml2"""

import logging
import multiprocessing
import os

import gunicorn.app.base
from app import application

# Configure the root logger so all modules (turso_mgmt, url_mgmt, etc.) emit
# at the level defined by the LOG_LEVEL env var (default: INFO).
# Set LOG_LEVEL=DEBUG locally to see BLOB-type debug lines.
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def number_of_workers():
    return (multiprocessing.cpu_count() * 2) + 1


class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


if __name__ == "__main__":
    options = {
        "bind": "%s:%s" % ("0.0.0.0", "8080"),
        "workers": number_of_workers(),
        "worker_tmp_dir": "/tmp",
        "loglevel": _log_level.lower(),
    }
    StandaloneApplication(application, options).run()
