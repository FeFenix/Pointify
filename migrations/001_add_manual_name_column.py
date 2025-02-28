from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise Exception("DATABASE_URL environment variable is not set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserPoints(Base):
    __tablename__ = "user_points"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True, nullable=True)
    username = Column(String, nullable=True)
    manual_name = Column(String, nullable=True)
    points = Column(Integer, default=0)

def upgrade():
    """Add manual_name column to user_points table"""
    with engine.connect() as connection:
        connection.execute("ALTER TABLE user_points ADD COLUMN manual_name VARCHAR")

if __name__ == "__main__":
    upgrade()
