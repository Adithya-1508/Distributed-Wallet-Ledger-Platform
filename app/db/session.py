from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings

# The connection pool to Postgres.pool_pre_ping quietly checks a connection is alive before use
engine = create_engine(settings.database_url, pool_pre_ping=True)

#SessionLocal is a factory that hands out DB sessions. 
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

#get_db() is a FastAPI dependency that gives requests their own sessions and guarantees it's closed afterwards.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()    

