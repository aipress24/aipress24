# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User

from ..models import IndividualWallet, WalletStatus


def test_indivividual_wallet(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    wallet = IndividualWallet(user=joe)
    db.session.add(wallet)
    db.session.flush()

    assert wallet.user == joe
    assert wallet.balance == 0
    assert wallet.status == WalletStatus.ACTIVE

    wallet.terminate()
    assert wallet.status == WalletStatus.TERMINATED
