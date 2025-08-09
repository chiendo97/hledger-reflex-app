"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from pydantic import BaseModel

from rxconfig import config

from .hledger_api import HLedgerClient


class PostingData(BaseModel):
    """Simplified posting representation for the UI layer (Pydantic)."""

    account: str
    amounts: list[str]
    amounts_display: str  # pre-joined string for UI (avoids joining on client)


class TransactionData(BaseModel):
    """Simplified transaction representation for the UI layer (Pydantic)."""

    index: int
    date: str
    description: str
    postings: list[PostingData]
    posting_count: int  # precomputed length for UI


class State(rx.State):
    """App state and data loaders for the dashboard."""

    # Data
    transactions: list[TransactionData] = []  # strongly typed simplified txns
    accountnames: list[str] = []  # list of account name strings

    # -------- Computed account groups --------
    @rx.var
    def assets(self) -> list[str]:
        return [a for a in self.accountnames if a.lower().startswith("asset")]

    @rx.var
    def liabilities(self) -> list[str]:
        return [a for a in self.accountnames if a.lower().startswith("liability")]

    @rx.var
    def income(self) -> list[str]:
        return [a for a in self.accountnames if a.lower().startswith("revenue")]

    @rx.var
    def expenses(self) -> list[str]:
        return [a for a in self.accountnames if a.lower().startswith("expense")]

    # -------- Loaders --------
    @rx.event
    def load_transactions(self):
        """Load and simplify transactions from the hledger API into typed structures."""
        raw_txns: list = []
        with HLedgerClient() as client:
            try:
                raw = client.get_transactions().model_dump(mode="json")
                if isinstance(raw, list):
                    raw_txns = raw
            except Exception:
                pass
        simplified: list[TransactionData] = []
        for t in raw_txns:
            postings: list[PostingData] = []
            for p in t.get("tpostings", []) or []:
                amounts_list: list[str] = []
                for a in p.get("pamount", []) or []:
                    qty_val = a.get("aquantity")
                    # Support nested structure (e.g. {aquantity: {decimalMantissa: "123"}}) gracefully
                    if isinstance(qty_val, dict):
                        qty = qty_val.get("decimalMantissa")
                    else:
                        qty = qty_val
                    comm = a.get("acommodity") or ""
                    if qty is None:
                        qty = ""
                    formatted = str(qty)
                    if comm:
                        formatted += f" {comm}"
                    amounts_list.append(formatted)
                postings.append(
                    PostingData(
                        account=p.get("paccount", ""),
                        amounts=amounts_list,
                        amounts_display=", ".join(amounts_list) if amounts_list else "",
                    )
                )
            simplified.append(
                TransactionData(
                    index=t.get("tindex", 0),
                    date=(t.get("tdate") or ""),
                    description=(t.get("tdescription") or ""),
                    postings=postings,
                    posting_count=len(postings),
                )
            )
        simplified.sort(key=lambda tx: tx.index, reverse=True)
        self.transactions = simplified
        yield

    @rx.event
    def load_accountnames(self):
        """Load account names list from the hledger API."""
        names: list[str] = []
        with HLedgerClient() as client:
            try:
                raw = client.get_accountnames().model_dump(mode="json")
                if isinstance(raw, list):
                    names = [str(n) for n in raw]
            except Exception:
                pass
        self.accountnames = names
        yield


# ---------------- UI Helpers ----------------
def nav() -> rx.Component:
    return rx.hstack(
        rx.link("Home", href="/"),
        rx.spacer(),
        rx.link("Transactions", href="/transaction"),
        rx.link("Balance Sheet", href="/balance-sheet"),
        rx.link("Income Statement", href="/income-statement"),
        width="100%",
        padding_y="8px",
    )


def section(title: str, content: rx.Component) -> rx.Component:
    return rx.vstack(
        rx.heading(title, size="6"),
        content,
        spacing="3",
        align_items="stretch",
        width="100%",
    )


# ---------------- Pages ----------------


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        nav(),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(
                "Get started by editing ",
                rx.code(f"{config.app_name}/{config.app_name}.py"),
                size="5",
            ),
            rx.hstack(
                rx.link(rx.button("Transactions"), href="/transaction"),
                rx.link(rx.button("Balance Sheet"), href="/balance-sheet"),
                rx.link(rx.button("Income Statement"), href="/income-statement"),
                spacing="3",
            ),
            spacing="5",
            justify="center",
            min_height="75vh",
        ),
    )


def transactions_page() -> rx.Component:
    return rx.container(
        nav(),
        rx.vstack(
            rx.hstack(
                rx.heading("Transactions", size="7"),
                rx.spacer(),
                rx.button("Reload", on_click=State.load_transactions),
                align_items="center",
                width="100%",
            ),
            rx.box(on_mount=State.load_transactions),
            rx.vstack(
                rx.foreach(
                    State.transactions,
                    lambda t: rx.box(
                        rx.hstack(
                            rx.badge(t.date, color_scheme="gray"),
                            rx.spacer(),
                            rx.text(t.description, weight="bold"),
                            width="100%",
                        ),
                        rx.vstack(
                            rx.foreach(
                                t.postings,
                                lambda p: rx.hstack(
                                    rx.text(p.account),
                                    rx.spacer(),
                                    rx.text(p.amounts_display),
                                    width="100%",
                                ),
                            ),
                            padding_left="16px",
                        ),
                        padding="10px",
                        border="1px solid",
                        border_color=rx.color("accent", 4),
                        border_radius="8px",
                        width="100%",
                    ),
                ),
                spacing="3",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding_y="16px",
    )


def balance_sheet_page() -> rx.Component:
    return rx.container(
        nav(),
        rx.vstack(
            rx.hstack(
                rx.heading("Balance Sheet", size="7"),
                rx.spacer(),
                rx.button("Reload", on_click=State.load_accountnames),  # type: ignore[arg-type]
                align_items="center",
                width="100%",
            ),
            rx.box(on_mount=State.load_accountnames),  # type: ignore[arg-type]
            rx.grid(
                section(
                    "Assets",
                    rx.vstack(
                        rx.foreach(State.assets, lambda a: rx.text(a)),
                        align_items="start",
                    ),
                ),
                section(
                    "Liabilities",
                    rx.vstack(
                        rx.foreach(State.liabilities, lambda a: rx.text(a)),
                        align_items="start",
                    ),
                ),
                columns="2",
                gap="4",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding_y="16px",
    )


def income_statement_page() -> rx.Component:
    return rx.container(
        nav(),
        rx.vstack(
            rx.hstack(
                rx.heading("Income Statement", size="7"),
                rx.spacer(),
                rx.button("Reload", on_click=State.load_accountnames),  # type: ignore[arg-type]
                align_items="center",
                width="100%",
            ),
            rx.box(on_mount=State.load_accountnames),  # type: ignore[arg-type]
            rx.grid(
                section(
                    "Revenue (Income)",
                    rx.vstack(
                        rx.foreach(State.income, lambda a: rx.text(a)),
                        align_items="start",
                    ),
                ),
                section(
                    "Expenses",
                    rx.vstack(
                        rx.foreach(State.expenses, lambda a: rx.text(a)),
                        align_items="start",
                    ),
                ),
                columns="2",
                gap="4",
                width="100%",
            ),
            spacing="4",
            width="100%",
        ),
        padding_y="16px",
    )


app = rx.App()
app.add_page(index)
app.add_page(transactions_page, route="/transaction")
app.add_page(balance_sheet_page, route="/balance-sheet")
app.add_page(income_statement_page, route="/income-statement")
