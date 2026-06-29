from __future__ import annotations

import socket
from urllib.error import HTTPError, URLError

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .config import DEFAULT_URL
from .scraper import scrape


def create_app() -> Flask:
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_object("aim_drachin.config")

    @app.get("/")
    def index():
        return render_template("index.html", default_url=DEFAULT_URL)

    @app.get("/api/scrape")
    def api_scrape():
        target = request.args.get("url", DEFAULT_URL)
        try:
            return jsonify({"ok": True, "data": scrape(target)})
        except (ValueError, HTTPError, URLError, socket.timeout, TimeoutError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Kesalahan internal: {exc}"}), 500

    return app
