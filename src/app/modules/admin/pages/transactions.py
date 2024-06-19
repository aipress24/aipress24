# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import select

from app.flask.lib.pages import page
from app.modules.wallet.models import WalletTransaction

from .. import table as t
from .base import AdminListPage
from .home import AdminHomePage

TABLE_COLUMNS = [
    {"name": "id", "label": "ID", "width": 50},
    {"name": "timestamp", "label": "Date/heure", "width": 50},
    {"name": "amount", "label": "Montant", "width": 50, "align": "right"},
    {"name": "from_wallet", "label": "De", "width": 50},
    {"name": "to_wallet", "label": "Vers", "width": 50},
]


class TransactionsTable(t.Table):
    def compose(self):
        for col in TABLE_COLUMNS:
            yield t.Column(**col)


class TransactionDataSource(t.DataSource):
    model_class = WalletTransaction

    def get_base_select(self) -> select:
        # from_wallet = aliased(BaseWallet)
        # to_wallet = aliased(BaseWallet)
        return (
            select(WalletTransaction)
            # .join(WalletTransaction.from_wallet)
            # .join(WalletTransaction.to_wallet)
            .order_by(WalletTransaction.timestamp.desc())
        )

    def add_search_filter(self, stmt):
        # if self.search:
        #     stmt = stmt.filter(User.last_name.ilike(f"{self.search}%"))
        return stmt

    def make_records(self, objects) -> list[dict]:
        result = []
        for obj in objects:
            record = {
                # "$url": url_for(obj),
                "$url": "",
                "id": obj.id,
                "timestamp": obj.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "amount": f"{obj.amount:0.2f} €",
                "from_wallet": obj.from_wallet.owner_name,
                "to_wallet": obj.to_wallet.owner_name,
            }
            result.append(record)
        return result


@page
class AdminTransactionsPage(AdminListPage):
    name = "transactions"
    label = "Transactions"
    title = "Transactions"

    template = "admin/pages/generic_table.j2"
    icon = "credit-card"

    parent = AdminHomePage

    ds_class = TransactionDataSource
    table_class = TransactionsTable
