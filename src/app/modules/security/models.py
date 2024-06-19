# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from flask_security import RoleMixin, UserMixin
# from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
# from sqlalchemy.orm import backref, relationship
#
# from app.models.base import Base
#
#
# class RolesUsers(Base):
#     __tablename__ = "aut_roles_users"
#     id = Column(Integer(), primary_key=True)
#     user_id = Column("user_id", Integer(), ForeignKey("aut_user.id"))
#     role_id = Column("role_id", Integer(), ForeignKey("aut_role.id"))
#
#
# class Role(Base, RoleMixin):
#     __tablename__ = "aut_role"
#     id = Column(Integer(), primary_key=True)
#     name = Column(String(80), unique=True)
#     description = Column(String(255))
#
#
# class User(Base, UserMixin):
#     __tablename__ = "aut_user"
#     id = Column(Integer, primary_key=True)
#     email = Column(String(255), unique=True)
#     username = Column(String(255), unique=True, nullable=True)
#     password = Column(String(255), nullable=False)
#
#     last_login_at = Column(DateTime())
#     current_login_at = Column(DateTime())
#     last_login_ip = Column(String(100))
#     current_login_ip = Column(String(100))
#     login_count = Column(Integer)
#
#     active = Column(Boolean())
#
#     fs_uniquifier = Column(String(255), unique=True, nullable=False)
#     confirmed_at = Column(DateTime())
#
#     roles = relationship(
#         Role, secondary="aut_roles_users", backref=backref("users", lazy="dynamic")
#     )
