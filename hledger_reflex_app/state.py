"""State module for ipay_reflex_app."""

import hashlib
import time
from collections import defaultdict
from typing import Final

import reflex as rx
from pydantic import BaseModel, computed_field

from .hledger_api import HLedgerClient


class PostingData(BaseModel):
    account: str
    amounts: list[str]
    amounts_display: str
    amounts_numeric: list[int] = []
    commodity: str

    palette: Final[list[str]] = [
        "tomato",
        "red",
        "crimson",
        "ruby",
        "pink",
        "orange",
        "amber",
        "gold",
        "bronze",
        "brown",
        "lime",
        "grass",
        "green",
        "olive",
        "mint",
        "teal",
        "cyan",
        "sky",
        "blue",
        "indigo",
        "violet",
        "purple",
        "plum",
    ]

    @computed_field
    def account_color(self) -> str:
        key = self.account.lower()
        h = hashlib.sha256(key.encode()).hexdigest()
        idx = int(h, 16) % len(self.palette)
        return self.palette[idx]

    @computed_field
    def amount_color(self) -> str:
        total_amount = sum(self.amounts_numeric)
        return "green" if total_amount > 0 else "red" if total_amount < 0 else "gray"


class TransactionData(BaseModel):
    index: int
    date: str
    description: str
    postings: list[PostingData]
    posting_count: int


class AccountBalanceData(BaseModel):
    name: str
    balance: int
    commodity: str

    @computed_field
    def color(self) -> str:
        if self.balance > 0:
            return "green"
        elif self.balance < 0:
            return "red"
        else:
            return "gray"


class State(rx.State):
    transactions: list[TransactionData] = []
    accountnames: list[str] = []
    loading: bool = False
    selected_month: str = ""
    search_description: str = ""
    search_account: str = ""
    nested_level: int = 3
    sort_by: str = "index"

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

    @rx.var
    def available_months(self) -> list[str]:
        months = {t.date[5:7] for t in self.transactions if len(t.date) >= 7}
        return sorted(months, reverse=True)

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
        else:
            res.sort(key=lambda t: t.index, reverse=True)
        return res

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
            AccountBalanceData(name=k, balance=-v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (item[1][0], item[0]))
        ]

    @rx.var
    def expense_balances(self) -> list[AccountBalanceData]:
        data = self._aggregate_balances("expense", apply_month=True)
        return [
            AccountBalanceData(name=k, balance=-v[0], commodity=v[1])
            for k, v in sorted(data.items(), key=lambda item: (-item[1][0], item[0]))
        ]

    @rx.event
    def load_transactions(self):
        start_time = time.time()
        print("Loading transactions...")
        self.loading = True
        yield
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
                commodity: str = ""
                for a in p.get("pamount", []) or []:
                    qty_val = a.get("aquantity")
                    try:
                        qty = int(qty_val.get("floatingPoint"))
                    except Exception:
                        qty = 0
                    comm = a.get("acommodity") or ""
                    if comm and not commodity:
                        commodity = comm
                    formatted = f"{qty:,}"
                    if comm:
                        formatted += f" {comm}"
                    amounts_list.append(formatted)
                    amounts_numeric.append(qty)
                account_name = p.get("paccount", "")
                postings.append(
                    PostingData(
                        account=account_name,
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
        self.loading = False
        print(
            "Loaded transactions in", (time.time() - start_time) * 1000, "milliseconds"
        )

    @rx.event
    def load_accountnames(self):
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
        q = self.router.url.query_parameters.get("query")
        if q:
            self.search_account = str(q)
        self.load_transactions()

    @rx.var
    def income_data(self) -> list:
        return [
            {"name": b.name, "value": b.balance, "fill": b.color}
            for b in self.income_balances
        ]

    @rx.var
    def expense_data(self) -> list:
        return [
            {"name": b.name, "value": b.balance, "fill": b.color}
            for b in self.expense_balances
        ]

    @rx.var
    def expense_level2_categories(self) -> list[str]:
        """All unique level-2 expense category keys (Expense:Category)."""
        cats: set[str] = set()
        for tx in self.transactions:
            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith("expense"):
                    continue
                parts = p.account.split(":")
                if len(parts) >= 2:
                    key = ":".join(parts[:2])
                else:
                    key = p.account
                cats.add(key)
        return sorted(cats)

    @rx.var
    def expense_level2_data(self) -> list:
        """Pie chart data for level 2 expense categories with totals and colors."""
        # Aggregate expenses by level 2 categories
        level2_totals: dict[str, int] = defaultdict(int)

        for tx in self.transactions:
            # Apply month filter if selected
            if self.selected_month and not tx.date[5:7] == self.selected_month:
                continue

            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith("expense"):
                    continue

                total_posting_amount = (
                    sum(p.amounts_numeric) if p.amounts_numeric else 0
                )

                # Get level 2 category key
                parts = p.account.split(":")
                if len(parts) >= 2:
                    key = ":".join(parts[:2])
                else:
                    key = p.account

                level2_totals[key] += total_posting_amount

        # Convert to pie chart format with colors
        palette = PostingData.palette
        result = []

        for category, total in level2_totals.items():
            # Convert to positive value for display (expenses are typically negative)
            value = -total if total < 0 else total

            # Generate consistent color for category
            h = hashlib.sha256(category.lower().encode()).hexdigest()
            idx = int(h, 16) % len(palette)
            color = palette[idx]

            if value > 0:  # Only include categories with actual expenses
                result.append({"name": category, "value": value, "fill": color})

        # Sort by value descending for better visualization
        result.sort(key=lambda x: x["value"], reverse=True)
        return result

    @rx.var
    def revenue_level2_categories(self) -> list[str]:
        """All unique level-2 revenue category keys (Revenue:Category)."""
        cats: set[str] = set()
        for tx in self.transactions:
            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith("revenue"):
                    continue
                parts = p.account.split(":")
                if len(parts) >= 2:
                    key = ":".join(parts[:2])
                else:
                    key = p.account
                cats.add(key)
        return sorted(cats)

    @rx.var
    def expense_level2_category_colors(self) -> list[tuple[str, str]]:
        """Deterministic color per level-2 category using same palette logic as postings."""
        palette = PostingData.palette
        result: list[tuple[str, str]] = []
        for cat in self.expense_level2_categories:
            h = hashlib.sha256(cat.lower().encode()).hexdigest()
            idx = int(h, 16) % len(palette)
            result.append((cat, palette[idx]))
        return result

    @rx.var
    def revenue_level2_category_colors(self) -> list[tuple[str, str]]:
        """Deterministic color per level-2 revenue category using same palette logic as postings."""
        palette = PostingData.palette
        result: list[tuple[str, str]] = []
        for cat in self.revenue_level2_categories:
            h = hashlib.sha256(cat.lower().encode()).hexdigest()
            idx = int(h, 16) % len(palette)
            result.append((cat, palette[idx]))
        return result

    @rx.var
    def monthly_expense_stacked(self) -> list[dict]:
        """Return list of dicts: one per month with summed expense amounts per level-2 category.

        Example element: {"month": "2025-01", "Expense:Food": 1200, "Expense:Rent": 2000}
        Amounts are positive numbers representing the magnitude of expenses in that month.
        """
        # month -> category -> amount (signed as in postings)
        month_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for tx in self.transactions:
            if len(tx.date) < 7:
                continue
            month = tx.date[:7]  # YYYY-MM
            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith("expense"):
                    continue
                total_posting_amount = (
                    sum(p.amounts_numeric) if p.amounts_numeric else 0
                )
                # Determine level-2 key
                parts = p.account.split(":")
                if len(parts) >= 2:
                    key = ":".join(parts[:2])
                else:
                    key = p.account
                month_cat[month][key] += total_posting_amount
        # Build unified list ensuring all categories present per row
        categories = self.expense_level2_categories
        rows: list[dict] = []
        for month in sorted(month_cat.keys()):
            row: dict[str, int | str] = {"month": month}
            for cat in categories:
                v = month_cat[month].get(cat, 0)
                # Convert to positive magnitude like other expense displays
                if v < 0:
                    v = -v
                row[cat] = v
            rows.append(row)
        print(rows)
        return rows

    @rx.var
    def monthly_revenue_stacked(self) -> list[dict]:
        """Return list of dicts: one per month with summed revenue amounts per level-2 category.

        Example element: {"month": "2025-01", "Revenue:Salary": 5000, "Revenue:Freelance": 1500}
        Amounts are positive numbers representing the magnitude of revenue in that month.
        """
        # month -> category -> amount (signed as in postings)
        month_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for tx in self.transactions:
            if len(tx.date) < 7:
                continue
            month = tx.date[:7]  # YYYY-MM
            for p in tx.postings:
                acct_lower = p.account.lower()
                if not acct_lower.startswith("revenue"):
                    continue
                total_posting_amount = (
                    sum(p.amounts_numeric) if p.amounts_numeric else 0
                )
                # Determine level-2 key
                parts = p.account.split(":")
                if len(parts) >= 2:
                    key = ":".join(parts[:2])
                else:
                    key = p.account
                month_cat[month][key] += total_posting_amount
        # Build unified list ensuring all categories present per row
        categories = self.revenue_level2_categories
        rows: list[dict] = []
        for month in sorted(month_cat.keys()):
            row: dict[str, int | str] = {"month": month}
            for cat in categories:
                v = month_cat[month].get(cat, 0)
                # Convert to positive magnitude (revenue is typically negative in accounting)
                if v < 0:
                    v = -v
                row[cat] = v
            rows.append(row)
        return rows
