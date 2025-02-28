import os
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging
from sqlalchemy.exc import OperationalError
from time import sleep

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

def create_db_engine(retries=3, delay=1):
    for attempt in range(retries):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
                connect_args={
                    'connect_timeout': 10,
                    'application_name': 'TelegramPointsBot',
                    'sslmode': 'require'
                }
            )
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return engine
        except OperationalError as e:
            if attempt == retries - 1:
                logger.error(f"Database connection failed: {e}")
                raise
            sleep(delay)
            delay *= 2

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserPoints(Base):
    __tablename__ = "user_points"
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True)
    username = Column(String)
    points = Column(Integer, default=0)

Base.metadata.create_all(bind=engine, checkfirst=True)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

class Database:
    def __init__(self):
        Base.metadata.create_all(bind=engine, checkfirst=True)

    def clear_all_points(self, chat_id: int):
        with get_db() as db:
            db.query(UserPoints).filter(UserPoints.chat_id == chat_id).update({"points": 0})

    def get_user_id_by_username(self, chat_id: int, username: str) -> int:
        with get_db() as db:
            user = db.query(UserPoints.user_id).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.username == username
            ).first()
            return user.user_id if user else None

    def get_all_users(self, chat_id: int) -> list:
        with get_db() as db:
            users = db.query(UserPoints.username).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.username.isnot(None)
            ).all()
            return [user.username for user in users]

    def add_user(self, chat_id: int, user_id: int, username: str) -> bool:
        try:
            with get_db() as db:
                user = db.query(UserPoints).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).first()

                if not user:
                    user = UserPoints(
                        chat_id=chat_id,
                        user_id=user_id,
                        points=0,
                        username=username
                    )
                    db.add(user)
                elif user.username != username:
                    user.username = username
                return True
        except Exception as e:
            logger.error(f"Add user error: {e}")
            return False

    def add_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        try:
            with get_db() as db:
                user = db.query(UserPoints).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).first()

                if not user:
                    user = UserPoints(
                        chat_id=chat_id,
                        user_id=user_id,
                        points=points,
                        username=username
                    )
                    db.add(user)
                else:
                    if username and user.username != username:
                        user.username = username
                    user.points += points
                return True
        except Exception as e:
            logger.error(f"Add points error: {e}")
            return False

    def subtract_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        try:
            with get_db() as db:
                user = db.query(UserPoints).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).first()

                if not user:
                    user = UserPoints(
                        chat_id=chat_id,
                        user_id=user_id,
                        points=0,
                        username=username
                    )
                    db.add(user)

                if username and user.username != username:
                    user.username = username
                user.points -= points
                return True
        except Exception as e:
            logger.error(f"Subtract points error: {e}")
            return False

    def get_user_points(self, chat_id: int, user_id: int) -> int:
        with get_db() as db:
            points = db.query(UserPoints.points).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.user_id == user_id
            ).scalar()
            return points or 0

    def get_top_users(self, chat_id: int, limit: int = 10) -> list:
        with get_db() as db:
            users = db.query(
                UserPoints.user_id,
                UserPoints.points,
                UserPoints.username
            ).filter(
                UserPoints.chat_id == chat_id
            ).order_by(
                UserPoints.points.desc()
            ).limit(limit).all()
            return [(user.user_id, {"points": user.points, "username": user.username}) for user in users]
