"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config

from .charts_page import charts_page
from .navigation import nav
from .state import State


# Refactored to use rx.table for Revenue and Expenses
def account_table(title: str, rows_var):
    return rx.cond(
        State.loading,
        rx.vstack(
            rx.heading(title, size="5"),
            rx.vstack(
                rx.foreach(
                    list(range(5)),
                    lambda _: rx.skeleton(
                        width="100%", height="28px", border_radius="6px"
                    ),
                ),
                spacing="2",
                width="100%",
            ),
            spacing="2",
            width="100%",
        ),
        rx.vstack(
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
                                rx.link(
                                    r.name,
                                    href=f"/transaction?query={r.name}",
                                    # Better text wrapping for long account names
                                    word_break="break-word",
                                    line_height="1.3",
                                )
                            ),
                            rx.table.cell(
                                rx.text(
                                    f"{r.balance:,} {r.commodity}",
                                    font_family="monospace",
                                    size="2",
                                    text_align="right",
                                    color=r.color,
                                    white_space="break-word",
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
        ),
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
                rx.link(rx.button("Charts"), href="/charts"),
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
            rx.heading("Transactions", size="7"),
            rx.vstack(
                # Primary filters row
                rx.flex(
                    rx.select(
                        State.available_years,
                        placeholder="Year",
                        on_change=State.set_selected_year,
                        value=State.selected_year,
                        min_width="80px",
                        flex="1",
                    ),
                    rx.select(
                        State.available_months,
                        placeholder="Month",
                        on_change=State.set_selected_month,
                        value=State.selected_month,
                        min_width="100px",
                        flex="1",
                    ),
                    rx.select(
                        ["index", "amount"],
                        placeholder="Sort by",
                        value=State.sort_by,
                        on_change=State.set_sort_by,
                        min_width="100px",
                        flex="1",
                    ),
                    spacing="2",
                    flex_wrap="wrap",
                    width="100%",
                    flex_direction=rx.breakpoints(initial="column", sm="row"),
                ),
                # Search filters row
                rx.flex(
                    rx.input(
                        placeholder="Search description",
                        value=State.search_description,
                        on_change=State.set_search_description,
                        flex="1",
                        min_width="150px",
                    ),
                    rx.input(
                        placeholder="Search account",
                        value=State.search_account,
                        on_change=State.set_search_account,
                        flex="1",
                        min_width="150px",
                    ),
                    spacing="2",
                    flex_wrap="wrap",
                    width="100%",
                    flex_direction=rx.breakpoints(initial="column", sm="row"),
                ),
                # Action buttons row
                rx.flex(
                    rx.button(
                        "Clear",
                        on_click=State.clear_transaction_filters,
                        variant="soft",
                        size="2",
                        width="100px",
                    ),
                    rx.button(
                        "Reload",
                        on_click=State.load_transactions,
                        loading=State.loading,
                        size="2",
                        width="100px",
                    ),
                    spacing="2",
                    width="100%",
                    flex_direction=rx.breakpoints(initial="column", sm="row"),
                    justify="end",
                    align_self="end",
                ),
                spacing="3",
                width="100%",
            ),
            # Initialize page (reads query + loads data)
            rx.cond(
                State.loading,
                rx.vstack(
                    rx.foreach(
                        list(range(6)),
                        lambda _: rx.box(
                            rx.vstack(
                                rx.skeleton(width="120px", height="16px"),
                                rx.skeleton(width="60%", height="16px"),
                                rx.skeleton(width="80%", height="16px"),
                                spacing="2",
                                width="100%",
                            ),
                            padding="12px",
                            border="1px solid",
                            border_color=rx.color("accent", 4),
                            border_radius="12px",
                            width="100%",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
                rx.vstack(
                    rx.foreach(
                        State.transactions_filtered,
                        lambda t: rx.box(
                            # Transaction header - mobile optimized
                            rx.vstack(
                                rx.flex(
                                    rx.badge(
                                        t.date,
                                        color_scheme="gray",
                                        size="2",
                                        flex_shrink="0",
                                    ),
                                    rx.text(
                                        t.description,
                                        size="3",
                                        weight="medium",
                                        text_overflow="ellipsis",
                                        overflow="hidden",
                                        white_space="nowrap",
                                        flex="1",
                                        margin_left="8px",
                                    ),
                                    width="100%",
                                    align="center",
                                    gap="2",
                                ),
                                spacing="1",
                                width="100%",
                            ),
                            # Postings section - improved mobile layout
                            rx.vstack(
                                rx.foreach(
                                    t.postings,
                                    lambda p: rx.vstack(
                                        # Desktop layout - side by side
                                        rx.flex(
                                            rx.text(
                                                p.account,
                                                weight="bold",
                                                color=rx.color(p.account_color, 11),
                                            ),
                                            rx.text(
                                                p.amounts_display,
                                                font_family="monospace",
                                                size="2",
                                                color=p.amount_color,
                                                flex_shrink="0",
                                                margin_left="8px",
                                            ),
                                            width="100%",
                                            align="center",
                                            flex_wrap="wrap",
                                            justify="between",
                                        ),
                                        spacing="2",
                                        width="100%",
                                        background=rx.color("gray", 1),
                                        border_radius="8px",
                                        margin_bottom="4px",
                                    ),
                                ),
                                spacing="2",
                                width="100%",
                                margin_top="8px",
                            ),
                            padding="12px",
                            border="1px solid",
                            border_color=rx.color("accent", 4),
                            border_radius="12px",
                            width="100%",
                            background=rx.color("gray", 1),
                            # Add hover effect for better UX
                            _hover={
                                "border_color": rx.color("accent", 6),
                                "shadow": "sm",
                            },
                            transition="all 0.2s ease",
                        ),
                    ),
                    spacing="3",
                    width="100%",
                ),
            ),
            spacing="4",
            width="100%",
        ),
    )


def balance_sheet_page() -> rx.Component:
    assets_table = account_table("Assets", State.asset_balances)
    liabilities_table = account_table("Liabilities", State.liability_balances)
    return rx.container(
        nav(),
        rx.vstack(
            rx.heading("Balance Sheet", size="7"),
            rx.flex(
                rx.select(
                    State.available_years,
                    placeholder="Year",
                    on_change=State.set_selected_year,
                    value=State.selected_year,
                ),
                rx.select(
                    [str(i) for i in range(1, 4)],
                    placeholder="Level",
                    on_change=State.set_nested_level,
                    value=State.level,
                ),
                rx.button(
                    "Reload",
                    on_click=State.load_transactions,
                    loading=State.loading,
                ),
                spacing="2",
                width="100%",
            ),
            rx.grid(
                assets_table,
                liabilities_table,
                columns=rx.breakpoints(initial="1", sm="2", lg="2"),
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
    income_table = account_table("Revenue", State.income_balances)
    expense_table = account_table("Expenses", State.expense_balances)
    return rx.container(
        nav(),
        rx.vstack(
            rx.heading("Income Statement", size="7"),
            rx.flex(
                rx.select(
                    State.available_years,
                    placeholder="Year",
                    on_change=State.set_selected_year,
                    value=State.selected_year,
                ),
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
                    value=State.level,
                ),
                rx.button(
                    "Reload",
                    on_click=State.load_transactions,
                    loading=State.loading,
                ),
                spacing="2",
                width="100%",
            ),
            rx.grid(
                income_table,
                expense_table,
                columns=rx.breakpoints(initial="1", sm="2", lg="2"),
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
app.add_page(
    transactions_page,
    route="/transaction",
    on_load=State.init_transactions_page,
)
app.add_page(
    balance_sheet_page,
    route="/balance-sheet",
    on_load=State.load_transactions,
)

app.add_page(
    charts_page,
    route="/charts",
    on_load=State.load_transactions,
)

app.add_page(
    income_statement_page,
    route="/income-statement",
    on_load=State.load_transactions,
)
