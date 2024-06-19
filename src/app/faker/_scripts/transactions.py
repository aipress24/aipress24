# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

from faker import Faker
from flask_super.registry import register

from app.flask.extensions import db
from app.models.auth import User
from app.modules.wallet.models import WalletTransaction

from .base import FakerScript

FAKE_LABELS = [
    "Achat de la lecture d'un article",
    "Achat de prestation",
]


@register
class TransactionFakerScript(FakerScript):
    name = "transactions"
    model_class = WalletTransaction

    def generate(self) -> None:
        fake = Faker()
        users = db.session.query(User).all()

        for _i in range(300):
            user1 = random.choice(users)
            user2 = random.choice(users)
            amount = random.randint(1, 100) * 5

            timestamp = fake.date_time_between(start_date="-1y", end_date="now")

            owner = user1
            label = random.choice(FAKE_LABELS)

            transaction = WalletTransaction(
                timestamp=timestamp,
                owner=owner,
                from_wallet=user1.wallet,
                to_wallet=user2.wallet,
                amount=amount,
                label=label,
                # description="Transaction",
            )
            db.session.add(transaction)

        db.session.flush()
