# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# import sqlalchemy as sa
# from arrow import Arrow
# from sqlalchemy import ForeignKey
# from sqlalchemy.orm import Mapped, declared_attr, mapped_column
# from sqlalchemy_utils import ArrowType
#
# from app.lib.names import to_snake_case
# from app.models.auth import User
# from app.models.base import Base
# from app.models.mixins import IdMixin, LifeCycleMixin
#
#
# class BaseRole(IdMixin, LifeCycleMixin, Base):
#     __allow_unmapped__ = True
#     __tablename__ = "rol_base_role"
#
#     #type: Mapped[str] = mapped_column()
#
#     user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
#     # user = relationship(User, back_populates="roles")
#
#     start_date: Mapped[Arrow] = mapped_column(ArrowType)
#     end_date: Mapped[Arrow] = mapped_column(ArrowType)
#
#     @declared_attr
#     def __mapper_args__(cls):
#         return {
#             "polymorphic_identity": to_snake_case(cls.__name__),
#             "polymorphic_on": cls.type,
#         }
#
#
# class Journalist(BaseRole):
#     __tablename__ = "rol_journalist"
#
#     id: Mapped[int] = mapped_column(
#         sa.BigInteger, sa.ForeignKey(BaseRole.id), primary_key=True
#     )
#
#
# class Expert(BaseRole):
#     __tablename__ = "rol_expert"
#
#     id: Mapped[int] = mapped_column(
#         sa.BigInteger, sa.ForeignKey(BaseRole.id), primary_key=True
#     )
#
#
# class Etudiant(BaseRole):
#     __tablename__ = "rol_student"
#
#     id: Mapped[int] = mapped_column(
#         sa.BigInteger, sa.ForeignKey(BaseRole.id), primary_key=True
#     )
#
#
# class ItTransformer(BaseRole):
#     __tablename__ = "rol_dev"
#
#     id: Mapped[int] = mapped_column(
#         sa.BigInteger, sa.ForeignKey(BaseRole.id), primary_key=True
#     )
