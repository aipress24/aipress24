# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# from app.modules.wallet.models import WalletTransaction

# language=jinja2
ROW_TEMPLATE = """
<tr class="bg-white">
  <td class="max-w-0 w-full px-6 py-4 whitespace-nowrap text-sm text-gray-900">
    <div class="flex">
      <a href="#" class="group inline-flex space-x-2 truncate text-sm">
        {{ icon("solid/banknotes", class="flex-shrink-0 h-5 w-5 text-gray-400 group-hover:text-gray-500") }}
        <p class="text-gray-500 truncate group-hover:text-gray-900">
          {{ item.label }}
        </p>
      </a>
    </div>
  </td>
  <td class="px-6 py-4 text-right whitespace-nowrap text-sm text-gray-500">
    <span class="text-gray-900 font-medium">{{ item.amount }} </span>
    EUR
  </td>
  <td class="hidden px-6 py-4 whitespace-nowrap text-sm text-gray-500 md:block">
      <span
          class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800 capitalize">
        success
      </span>
  </td>
  <td class="px-6 py-4 text-right whitespace-nowrap text-sm text-gray-500">
    <time datetime="2020-07-11">{{ item.timestamp.format("YYYY-MM-DD HH:mm") }}</time>
  </td>
</tr>
"""


# class RecentTransactionsDataSource(DataSource):
#     def query(self):
#         user: User = g.user
#         wallet = user.wallet
#         if not user.wallet:
#             return select(WalletTransaction).where(False)

#         return (
#             select(WalletTransaction)
#             .where(
#                 or_(
#                     WalletTransaction.from_wallet_id == wallet.id,
#                     WalletTransaction.to_wallet_id == wallet.id,
#                 )
#             )
#             .order_by(WalletTransaction.timestamp.desc())
#             .limit(10)
#         )

#     def get_items(self):
#         query = self.query().limit(10)
#         return list(db.session.scalars(query))

#     def get_count(self):
#         # FIXME:
#         return len(list(db.session.scalars(self.query())))


# @define
# class RecentTransactionsTable(Table):
#     id = "recent-transactions-table"
#     columns = [
#         {"name": "label", "label": "Transaction"},
#         {"name": "amount", "label": "Montant"},
#         {"name": "status", "label": "Statut"},
#         {"name": "timestamp", "label": "Date"},
#     ]
#     row_template = ROW_TEMPLATE
#     data_source = RecentTransactionsDataSource()
