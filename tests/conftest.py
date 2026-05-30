import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.base import Base
from app.db import models
from app.db.session import get_db
from app.main import app


#WE ARE TESTING WITH A TEST DB AND POINTING THE ORM AND APP TO IT

TEST_DATABASE_URL = make_url(settings.database_url).set(database='wallet_test')
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine, 
    autoflush=False, 
    autocommit=False, 
    join_transaction_mode="create_savepoint",)


@pytest.fixture(scope="session", autouse=True)
def _setup_schema():
    """Create every table once before the suite, drop it all after"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Session:
    """Each test runs inside a transaction that is rolled back afterwards"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db) -> TestClient:
    def override_get_db():
        yield db


    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:    
        yield c
    app.dependency_overrides.clear()    


