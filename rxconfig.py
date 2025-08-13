import reflex as rx

config = rx.Config(
    app_name="hledger_reflex_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)