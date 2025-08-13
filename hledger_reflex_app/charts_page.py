# charts_page.py
# Page for displaying useful charts (bar, pie) based on app data

import reflex as rx

from .navigation import nav
from .state import State


def charts_page() -> rx.Component:
    """Page displaying simple bar and pie chart-like tables for income and expenses."""

    return rx.container(
        nav(),
        rx.heading("Charts Overview", size="7"),
        rx.grid(
            rx.vstack(
                rx.heading("Monthly Revenue (Stacked Bar)", size="5"),
                rx.recharts.bar_chart(
                    rx.foreach(
                        State.revenue_level2_category_colors,
                        lambda cat_color: rx.recharts.bar(
                            data_key=cat_color[0],
                            stack_id="revenue",
                            fill=rx.color(cat_color[1], 8),
                        ),
                    ),
                    rx.recharts.x_axis(data_key="month", interval=0),
                    rx.recharts.y_axis(),
                    rx.recharts.legend(),
                    data=State.monthly_revenue_stacked,
                    width="100%",
                    height=400,
                ),
            ),
            rx.vstack(
                rx.heading("Level 2 Expenses (Pie Chart)", size="5"),
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=State.expense_level2_data,
                        data_key="value",
                        name_key="name",
                        label=True,
                    ),
                    rx.recharts.legend(),
                    width="100%",
                    height=300,
                ),
            ),
            rx.vstack(
                rx.heading("Monthly Expenses (Stacked Bar)", size="5"),
                rx.recharts.bar_chart(
                    rx.foreach(
                        State.expense_level2_category_colors,
                        lambda cat_color: rx.recharts.bar(
                            data_key=cat_color[0],
                            stack_id="expenses",
                            fill=rx.color(cat_color[1], 8),
                        ),
                    ),
                    rx.recharts.x_axis(data_key="month"),
                    rx.recharts.y_axis(),
                    rx.recharts.legend(),
                    data=State.monthly_expense_stacked,
                    width="100%",
                    height=400,
                ),
            ),
            columns=rx.breakpoints(initial="1", sm="2", lg="2"),
            gap="6",
            width="100%",
            spacing="4",
        ),
        spacing="4",
        width="100%",
        padding_y="16px",
    )
