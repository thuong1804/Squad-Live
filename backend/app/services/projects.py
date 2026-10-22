from sqlalchemy import select

from app.core.errors import DomainError, conflict
from app.models.entities import Project, WorkItem


def project_for(session, project_id: str, user: str, *, lock=False):
    query = select(Project).where(Project.id == project_id)
    if lock:
        query = query.with_for_update()
    project = session.scalar(query)
    if project is None or project.owner != user:
        raise DomainError(404, "not_found", "Project not found")
    return project


def item_for(session, item_id: str, user: str, *, lock=False):
    query = select(WorkItem).where(WorkItem.id == item_id)
    if lock:
        query = query.with_for_update()
    item = session.scalar(query)
    if item is None:
        raise DomainError(404, "not_found", "Work item not found")
    project_for(session, item.project_id, user)
    return item


def create_project(session, data, user):
    project = Project(**data.model_dump(), owner=user)
    session.add(project)
    session.flush()
    return project


def update_project(session, project_id, data, user):
    project = project_for(session, project_id, user, lock=True)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    session.flush()
    return project


def create_item(session, project_id, data, user):
    project = project_for(session, project_id, user, lock=True)
    if project.status != "active":
        conflict("Archived projects cannot receive work items")
    item = WorkItem(**data.model_dump(), project_id=project_id, creator=user)
    session.add(item)
    session.flush()
    return item
