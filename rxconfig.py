import os

import reflex as rx

API_URL = os.getenv("API_URL", "http://localhost:8000")

config = rx.Config(
    app_name="hledger_reflex_app",
    api_url=API_URL,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)

