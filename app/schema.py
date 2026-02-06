from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text)
    color = Column(Text, nullable=False, server_default=text("'#94a3b8'"))


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, unique=True)
    hashed_password = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    is_active = Column(Integer, nullable=False, server_default=text("1"))

    __table_args__ = (
        CheckConstraint("role IN ('Viewer', 'Editor', 'Admin')", name="ck_users_role"),
    )


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)
    notes = Column(Text)
    vendor_id = Column(Integer, ForeignKey("vendors.id"))
    created_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class IPAsset(Base):
    __tablename__ = "ip_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(Text, nullable=False, unique=True)
    type = Column(Text, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"))
    host_id = Column(Integer, ForeignKey("hosts.id"))
    notes = Column(Text)
    archived = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        CheckConstraint("type IN ('VM', 'OS', 'BMC', 'VIP', 'OTHER')", name="ck_ip_assets_type"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(Text, nullable=True)
    target_type = Column(Text, nullable=False)
    target_id = Column(Integer, nullable=False)
    target_label = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    changes = Column(Text)
    created_at = Column(Text, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
