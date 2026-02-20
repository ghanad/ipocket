from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterable, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app import schema as db_schema
from app.dependencies import create_db_session
from app.models import Project, Tag, Vendor
from app.utils import DEFAULT_PROJECT_COLOR, DEFAULT_TAG_COLOR, normalize_hex_color


def _to_project(model: db_schema.Project) -> Project:
    return Project(
        id=int(model.id),
        name=str(model.name),
        description=model.description,
        color=model.color,
    )


def _to_vendor(model: db_schema.Vendor) -> Vendor:
    return Vendor(id=int(model.id), name=str(model.name))


def _to_tag(model: db_schema.Tag) -> Tag:
    return Tag(id=int(model.id), name=str(model.name), color=str(model.color))


@contextmanager
def _session_scope(connection_or_session: sqlite3.Connection | Session):
    if isinstance(connection_or_session, Session):
        yield connection_or_session
        return

    # Backward-compatible shim for non-migrated call sites that still pass sqlite3.
    session = create_db_session()
    try:
        yield session
    finally:
        session.close()


def create_project(
    connection_or_session: sqlite3.Connection | Session,
    name: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> Project:
    normalized_color = color or DEFAULT_PROJECT_COLOR
    with _session_scope(connection_or_session) as session:
        model = db_schema.Project(
            name=name,
            description=description,
            color=normalized_color,
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        return _to_project(model)


def get_project_by_id(
    connection_or_session: sqlite3.Connection | Session, project_id: int
) -> Optional[Project]:
    with _session_scope(connection_or_session) as session:
        model = session.get(db_schema.Project, project_id)
        return _to_project(model) if model else None


def update_project(
    connection_or_session: sqlite3.Connection | Session,
    project_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> Optional[Project]:
    with _session_scope(connection_or_session) as session:
        model = session.get(db_schema.Project, project_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        if color is not None:
            model.color = color
        session.commit()
        session.refresh(model)
        return _to_project(model)


def list_projects(
    connection_or_session: sqlite3.Connection | Session,
) -> Iterable[Project]:
    with _session_scope(connection_or_session) as session:
        models = session.scalars(
            select(db_schema.Project).order_by(db_schema.Project.name)
        ).all()
        return [_to_project(model) for model in models]


def delete_project(
    connection_or_session: sqlite3.Connection | Session, project_id: int
) -> bool:
    with _session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.IPAsset)
            .where(db_schema.IPAsset.project_id == project_id)
            .values(project_id=None)
        )
        result = session.execute(
            delete(db_schema.Project).where(db_schema.Project.id == project_id)
        )
        session.commit()
        return result.rowcount > 0


def list_project_ip_counts(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[int, int]:
    with _session_scope(connection_or_session) as session:
        rows = session.execute(
            select(db_schema.IPAsset.project_id, func.count().label("total"))
            .where(
                db_schema.IPAsset.project_id.is_not(None),
                db_schema.IPAsset.archived == 0,
            )
            .group_by(db_schema.IPAsset.project_id)
        ).all()
        return {int(project_id): int(total) for project_id, total in rows}


def create_vendor(
    connection_or_session: sqlite3.Connection | Session, name: str
) -> Vendor:
    with _session_scope(connection_or_session) as session:
        model = db_schema.Vendor(name=name)
        session.add(model)
        session.commit()
        session.refresh(model)
        return _to_vendor(model)


def list_vendors(
    connection_or_session: sqlite3.Connection | Session,
) -> Iterable[Vendor]:
    with _session_scope(connection_or_session) as session:
        models = session.scalars(
            select(db_schema.Vendor).order_by(db_schema.Vendor.name)
        ).all()
        return [_to_vendor(model) for model in models]


def list_vendor_ip_counts(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[int, int]:
    with _session_scope(connection_or_session) as session:
        rows = session.execute(
            select(db_schema.Host.vendor_id, func.count().label("total"))
            .join(db_schema.IPAsset, db_schema.IPAsset.host_id == db_schema.Host.id)
            .where(
                db_schema.Host.vendor_id.is_not(None),
                db_schema.IPAsset.archived == 0,
            )
            .group_by(db_schema.Host.vendor_id)
        ).all()
        return {int(vendor_id): int(total) for vendor_id, total in rows}


def get_vendor_by_id(
    connection_or_session: sqlite3.Connection | Session, vendor_id: int
) -> Optional[Vendor]:
    with _session_scope(connection_or_session) as session:
        model = session.get(db_schema.Vendor, vendor_id)
        return _to_vendor(model) if model else None


def get_vendor_by_name(
    connection_or_session: sqlite3.Connection | Session, name: str
) -> Optional[Vendor]:
    with _session_scope(connection_or_session) as session:
        model = session.scalar(
            select(db_schema.Vendor).where(db_schema.Vendor.name == name)
        )
        return _to_vendor(model) if model else None


def update_vendor(
    connection_or_session: sqlite3.Connection | Session, vendor_id: int, name: str
) -> Optional[Vendor]:
    with _session_scope(connection_or_session) as session:
        result = session.execute(
            update(db_schema.Vendor)
            .where(db_schema.Vendor.id == vendor_id)
            .values(name=name, updated_at=func.current_timestamp())
        )
        session.commit()
        if result.rowcount == 0:
            return None
        model = session.get(db_schema.Vendor, vendor_id)
        return _to_vendor(model) if model else None


def delete_vendor(
    connection_or_session: sqlite3.Connection | Session, vendor_id: int
) -> bool:
    with _session_scope(connection_or_session) as session:
        session.execute(
            update(db_schema.Host)
            .where(db_schema.Host.vendor_id == vendor_id)
            .values(vendor_id=None)
        )
        result = session.execute(
            delete(db_schema.Vendor).where(db_schema.Vendor.id == vendor_id)
        )
        session.commit()
        return result.rowcount > 0


def create_tag(
    connection_or_session: sqlite3.Connection | Session,
    name: str,
    color: Optional[str] = None,
) -> Tag:
    normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
    with _session_scope(connection_or_session) as session:
        model = db_schema.Tag(name=name, color=normalized_color)
        session.add(model)
        session.commit()
        session.refresh(model)
        return _to_tag(model)


def list_tags(connection_or_session: sqlite3.Connection | Session) -> Iterable[Tag]:
    with _session_scope(connection_or_session) as session:
        models = session.scalars(
            select(db_schema.Tag).order_by(db_schema.Tag.name)
        ).all()
        return [_to_tag(model) for model in models]


def list_tag_ip_counts(
    connection_or_session: sqlite3.Connection | Session,
) -> dict[int, int]:
    with _session_scope(connection_or_session) as session:
        rows = session.execute(
            select(db_schema.IPAssetTag.tag_id, func.count().label("total"))
            .join(
                db_schema.IPAsset,
                db_schema.IPAsset.id == db_schema.IPAssetTag.ip_asset_id,
            )
            .where(db_schema.IPAsset.archived == 0)
            .group_by(db_schema.IPAssetTag.tag_id)
        ).all()
        return {int(tag_id): int(total) for tag_id, total in rows}


def get_tag_by_id(
    connection_or_session: sqlite3.Connection | Session, tag_id: int
) -> Optional[Tag]:
    with _session_scope(connection_or_session) as session:
        model = session.get(db_schema.Tag, tag_id)
        return _to_tag(model) if model else None


def get_tag_by_name(
    connection_or_session: sqlite3.Connection | Session, name: str
) -> Optional[Tag]:
    with _session_scope(connection_or_session) as session:
        model = session.scalar(select(db_schema.Tag).where(db_schema.Tag.name == name))
        return _to_tag(model) if model else None


def update_tag(
    connection_or_session: sqlite3.Connection | Session,
    tag_id: int,
    name: str,
    color: Optional[str] = None,
) -> Optional[Tag]:
    normalized_color = normalize_hex_color(color) or DEFAULT_TAG_COLOR
    with _session_scope(connection_or_session) as session:
        result = session.execute(
            update(db_schema.Tag)
            .where(db_schema.Tag.id == tag_id)
            .values(
                name=name,
                color=normalized_color,
                updated_at=func.current_timestamp(),
            )
        )
        session.commit()
        if result.rowcount == 0:
            return None
        model = session.get(db_schema.Tag, tag_id)
        return _to_tag(model) if model else None


def delete_tag(
    connection_or_session: sqlite3.Connection | Session, tag_id: int
) -> bool:
    with _session_scope(connection_or_session) as session:
        session.execute(
            delete(db_schema.IPAssetTag).where(db_schema.IPAssetTag.tag_id == tag_id)
        )
        result = session.execute(
            delete(db_schema.Tag).where(db_schema.Tag.id == tag_id)
        )
        session.commit()
        return result.rowcount > 0
