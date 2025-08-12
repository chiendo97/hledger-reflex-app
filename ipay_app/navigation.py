import reflex as rx


# ---------------- UI Helpers ----------------
def nav() -> rx.Component:
    return rx.hstack(
        rx.link("Home", href="/"),
        rx.spacer(),
        rx.link("Transactions", href="/transaction"),
        rx.link("Balance Sheet", href="/balance-sheet"),
        rx.link("Charts", href="/charts"),
        rx.link("Income Statement", href="/income-statement"),
        width="100%",
        align="center",
    )
