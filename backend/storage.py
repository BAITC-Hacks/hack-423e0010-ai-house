import secrets
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, Integer, String, Text, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL


class Base(DeclarativeBase):
    pass


class CatalogRecord(Base):
    __tablename__ = 'contractors'
    id = Column(String, primary_key=True)
    version = Column(String, index=True, nullable=False)
    payload = Column(JSON, nullable=False)


class RequestRecord(Base):
    __tablename__ = 'selection_requests'
    id = Column(String, primary_key=True)
    owner = Column(String, index=True, nullable=False)
    revision = Column(Integer, default=1, nullable=False)
    draft = Column(JSON, nullable=False)


class RunRecord(Base):
    __tablename__ = 'recommendation_runs'
    id = Column(String, primary_key=True)
    request_id = Column(String, index=True, nullable=False)
    owner = Column(String, index=True, nullable=False)
    created_at = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)


class MessageRecord(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)


class VectorRecord(Base):
    __tablename__ = 'profile_embeddings'
    key = Column(String, primary_key=True)
    vector = Column(JSON, nullable=False)


class Store:
    def __init__(self, url=DATABASE_URL):
        options = {'check_same_thread': False} if url.startswith('sqlite') else {}
        self.engine = create_engine(url, connect_args=options, pool_pre_ping=True)
        self.session = sessionmaker(self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)

    def create_request(self, owner, draft):
        with self.session.begin() as s:
            item = RequestRecord(id=secrets.token_urlsafe(18), owner=owner, draft=draft, revision=1)
            s.add(item)
        return self.serialize_request(item)

    @staticmethod
    def serialize_request(item):
        return {'id': item.id, 'revision': item.revision, 'draft': item.draft}

    def get_request(self, request_id, owner):
        with self.session() as s:
            item = s.get(RequestRecord, request_id)
            if not item or item.owner != owner:
                return None
            return self.serialize_request(item)

    def update_request(self, request_id, owner, revision, draft):
        with self.session.begin() as s:
            changed = s.execute(update(RequestRecord).where(RequestRecord.id == request_id, RequestRecord.owner == owner, RequestRecord.revision == revision).values(draft=draft, revision=revision + 1))
            if changed.rowcount != 1:
                return None
        return self.get_request(request_id, owner)

    def save_run(self, request_id, owner, result):
        run_id = secrets.token_urlsafe(18)
        result = {**result, 'run_id': run_id, 'created_at': datetime.now(timezone.utc).isoformat()}
        with self.session.begin() as s:
            s.add(RunRecord(id=run_id, request_id=request_id, owner=owner, created_at=result['created_at'], payload=result))
        return result

    def runs(self, request_id, owner, limit=20):
        with self.session() as s:
            items = s.scalars(select(RunRecord).where(RunRecord.request_id == request_id, RunRecord.owner == owner).order_by(RunRecord.created_at.desc()).limit(limit)).all()
            return [i.payload for i in items]

    def get_run(self, run_id, request_id, owner):
        with self.session() as s:
            run = s.get(RunRecord, run_id)
            if not run or run.owner != owner or run.request_id != request_id:
                return None
            return run.payload

    def add_message(self, request_id, role, content):
        with self.session.begin() as s:
            s.add(MessageRecord(request_id=request_id, role=role, content=content))

    def messages(self, request_id, limit=60):
        with self.session() as s:
            rows = s.scalars(select(MessageRecord).where(MessageRecord.request_id == request_id).order_by(MessageRecord.id.desc()).limit(limit)).all()
            return [{'role': r.role, 'content': r.content} for r in reversed(rows)]

    def vector(self, key):
        with self.session() as s:
            item = s.get(VectorRecord, key)
            return item.vector if item else None

    def put_vector(self, key, vector):
        with self.session.begin() as s:
            s.merge(VectorRecord(key=key, vector=vector))

