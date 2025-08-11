"""Welcome to Reflex! This file outlines the steps to create a basic app."""

from collections import defaultdict

import reflex as rx
from pydantic import BaseModel

from rxconfig import config

from .hledger_api import HLedgerClient


class PostingData(BaseModel):
    """Simplified posting representation for the UI layer (Pydantic)."""

    account: str
    amounts: list[str]
    amounts_display: str  # pre-joined string for UI (avoids joining on client)
    amounts_numeric: list[int] = []  # parsed numeric quantities (best-effort)
    commodity: str  # first commodity if present (empty string if none)


class TransactionData(BaseModel):
    """Simplified transaction representation for the UI layer (Pydantic)."""

    index: int
    date: str
    description: str
    postings: list[PostingData]
    posting_count: int  # precomputed length for UI


class AccountBalanceData(BaseModel):
    name: str
    balance: int
    commodity: str


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

    # -------- Filter / UI state --------
    selected_month: str = ""  # format "01".."12"; empty => all
    search_description: str = ""
    search_account: str = ""
    nested_level: int = 3  # depth for grouping accounts
    sort_by: str = "index"  # sorting criterion: 'index' (default) or 'amount'

    # -------- Events to update filters --------
    @rx.event
    def set_selected_month(self, month: str):
        self.selected_month = month

    @rx.event
    def set_search_description(self, text: str):
        self.search_description = text.strip()

    @rx.event
    def set_search_account(self, text: str):
        self.search_account = text.strip()

    @rx.event
    def set_nested_level(self, level: str):
        try:
            self.nested_level = max(1, min(10, int(level)))
        except ValueError:
            self.nested_level = 1

    @rx.event
    def set_sort_by(self, value: str):
        if value in {"index", "amount"}:
            self.sort_by = value
        else:
            self.sort_by = "index"

    @rx.event
    def clear_transaction_filters(self):
        self.selected_month = ""
        self.search_description = ""
        self.search_account = ""

    # -------- Derived filter option lists --------
    @rx.var
    def available_months(self) -> list[str]:
        months = {t.date[5:7] for t in self.transactions if len(t.date) >= 7}
        return sorted(months, reverse=True)

    # -------- Filtered transactions --------
    @rx.var
    def transactions_filtered(self) -> list[TransactionData]:
        desc = self.search_description.lower()
        acct = self.search_account.lower()
        res: list[TransactionData] = []
        for tx in self.transactions:
            if self.selected_month and not tx.date[5:7] == self.selected_month:
                continue
            if desc and desc not in tx.description.lower():
                continue
            if acct and not any(acct in p.account.lower() for p in tx.postings):
                continue
            res.append(tx)
        # Apply sorting
        if self.sort_by == "amount":

            def txn_max_amount(t: TransactionData) -> int:
                m = 0
                for p in t.postings:
                    if p.amounts_numeric:
                        pm = max(p.amounts_numeric)
                        if pm > m:
                            m = pm
                return m

            res.sort(key=lambda t: (txn_max_amount(t), t.index), reverse=True)
        else:  # default index (already descending order in load, but re-ensure)
            res.sort(key=lambda t: t.index, reverse=True)
        return res

    # -------- Account balance aggregation helpers --------
    def _aggregate_balances(
        self, root_prefix: str, apply_month: bool = True
    ) -> dict[str, tuple[int, str]]:
        balances: dict[str, int] = defaultdict(int)
        commodities: dict[str, str] = {}
        for tx in reversed(self.transactions):
            if (
                apply_month
                and self.selected_month
                and not tx.date[5:7] == self.selected_month
            ):
                continue
            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith(root_prefix):
                    continue
                total_posting_amount = (
                    sum(p.amounts_numeric) if p.amounts_numeric else 0.0
                )
                try:
                    total_posting_amount_int = int(total_posting_amount)
                except Exception:
                    total_posting_amount_int = 0
                parts = p.account.split(":")
                group_key = (
                    ":".join(parts[: self.nested_level])
                    if self.nested_level <= len(parts)
                    else p.account
                )
                balances[group_key] += total_posting_amount_int
                if group_key not in commodities and p.commodity:
                    commodities[group_key] = p.commodity
        return {k: (balances[k], commodities.get(k) or "") for k in balances}

    @rx.var
    def asset_balances(self) -> list[AccountBalanceData]:
        data = self._aggregate_balances("asset", apply_month=False)
        return [
            AccountBalanceData(name=k, balance=v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (-item[1][0], item[0]))
        ]

    @rx.var
    def liability_balances(self) -> list[AccountBalanceData]:
        data = self._aggregate_balances("liability", apply_month=False)
        return [
            AccountBalanceData(name=k, balance=v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (-item[1][0], item[0]))
        ]

    @rx.var
    def income_balances(self) -> list[AccountBalanceData]:
        data = self._aggregate_balances("revenue", apply_month=True)
        return [
            AccountBalanceData(name=k, balance=v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (-item[1][0], item[0]))
        ]

    @rx.var
    def expense_balances(self) -> list[AccountBalanceData]:
        data = self._aggregate_balances("expense", apply_month=True)
        return [
            AccountBalanceData(name=k, balance=v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (-item[1][0], item[0]))
        ]

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
                amounts_numeric: list[int] = []
                commodity: str = ""  # ensure always a string
                for a in p.get("pamount", []) or []:
                    qty_val = a.get("aquantity")
                    qty = int(qty_val.get("floatingPoint"))
                    comm = a.get("acommodity") or ""
                    if comm and not commodity:
                        commodity = comm
                    formatted = str(qty)
                    if comm:
                        formatted += f" {comm}"
                    amounts_list.append(formatted)
                    # numeric parse
                    amounts_numeric.append(int(qty))
                postings.append(
                    PostingData(
                        account=p.get("paccount", ""),
                        amounts=amounts_list,
                        amounts_display=", ".join(amounts_list) if amounts_list else "",
                        amounts_numeric=amounts_numeric,
                        commodity=commodity,
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

    @rx.event
    def init_transactions_page(self):
        """Initialize transactions page: pick up ?query=... and load transactions."""
        q = self.router.url.query_parameters.get("query")
        if q:
            self.search_account = str(q)

        self.load_transactions()


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


# Refactored to use rx.table for Revenue and Expenses
def account_table(title: str, rows_var):
    return rx.vstack(
        rx.heading(title, size="5"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Account"),
                    rx.table.column_header_cell("Amount", text_align="right"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    rows_var,
                    lambda r: rx.table.row(
                        rx.table.cell(
                            rx.link(r.name, href=f"/transaction?query={r.name}")
                        ),
                        rx.table.cell(
                            rx.text(
                                f"{r.balance:,} {r.commodity}",
                                font_family="monospace",
                                size="2",
                                text_align="right",
                            )
                        ),
                    ),
                )
            ),
            variant="surface",
            size="3",
            width="100%",
        ),
        spacing="2",
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
    filters_bar = rx.hstack(
        rx.select(
            State.available_months,
            placeholder="Month",
            on_change=State.set_selected_month,
            value=State.selected_month,
        ),
        rx.input(
            placeholder="Search description",
            value=State.search_description,
            on_change=State.set_search_description,
        ),
        rx.input(
            placeholder="Search account",
            value=State.search_account,
            on_change=State.set_search_account,
        ),
        rx.select(
            ["index", "amount"],
            placeholder="Sort by",
            value=State.sort_by,
            on_change=State.set_sort_by,
        ),
        rx.button("Clear", on_click=State.clear_transaction_filters),
        spacing="2",
        width="100%",
    )
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
            # Initialize page (reads query + loads data)
            rx.box(on_mount=State.init_transactions_page),
            filters_bar,
            rx.vstack(
                rx.foreach(
                    State.transactions_filtered,
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
    controls = rx.hstack(
        rx.select(
            [str(i) for i in range(1, 4)],
            placeholder="Level",
            on_change=State.set_nested_level,
            value=str(State.nested_level),
        ),
        rx.button("Reload", on_click=State.load_transactions),
        spacing="2",
        width="100%",
    )

    assets_table = account_table("Assets", State.asset_balances)
    liabilities_table = account_table("Liabilities", State.liability_balances)
    return rx.container(
        nav(),
        rx.vstack(
            rx.hstack(
                rx.heading("Balance Sheet", size="7"),
                rx.spacer(),
                controls,
                width="100%",
            ),
            rx.box(on_mount=State.load_accountnames),
            rx.grid(
                assets_table,
                liabilities_table,
                columns="2",
                gap="6",
                width="100%",
                spacing="4",
            ),
            spacing="4",
            width="100%",
        ),
        padding_y="16px",
    )


def income_statement_page() -> rx.Component:
    controls = rx.hstack(
        rx.select(
            State.available_months,
            placeholder="Month",
            on_change=State.set_selected_month,
            value=State.selected_month,
        ),
        rx.select(
            [str(i) for i in range(1, 4)],
            placeholder="Level",
            on_change=State.set_nested_level,
            value=str(State.nested_level),
        ),
        rx.button("Reload", on_click=State.load_transactions),
        spacing="2",
        width="100%",
    )

    income_table = account_table("Revenue", State.income_balances)
    expense_table = account_table("Expenses", State.expense_balances)
    return rx.container(
        nav(),
        rx.vstack(
            rx.hstack(
                rx.heading("Income Statement", size="7"),
                rx.spacer(),
                controls,
                width="100%",
            ),
            rx.box(on_mount=State.load_accountnames),
            rx.grid(
                income_table,
                expense_table,
                columns="2",
                gap="6",
                width="100%",
                spacing="4",
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
