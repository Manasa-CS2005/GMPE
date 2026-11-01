import os

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from dotenv import load_dotenv

load_dotenv()


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    return os.getenv("LIFELOG_AUTH_DATABASE_URL", "sqlite:///./lifelog.db")


def make_engine(url: str | None = None) -> Engine:
    selected_url = url or database_url()
    options: dict[str, object] = {"pool_pre_ping": True}
    if selected_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(selected_url, **options)

    if selected_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _record) -> None:
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
