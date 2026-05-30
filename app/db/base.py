# Every table will subclass Base. Base.metadata becomes the registry of all tables. In other words, it maps all the Python classes to their database tables
# Alembic reads it to autogenerate migrations

from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass