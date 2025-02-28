import os
from sqlalchemy import create_engine, Column, Integer, String, BigInteger, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import logging
from sqlalchemy.exc import OperationalError
from time import sleep

# Configure logging with less verbose output
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL is None:
    raise Exception("DATABASE_URL environment variable is not set")

def create_db_engine(retries=3, delay=1):
    """Create database engine with optimized connection pool"""
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
                    'connect_timeout': 20,  # Increase connect timeout
                    'application_name': 'TelegramPointsBot',
                    'sslmode': 'require'
                }
            )

            # Test the connection
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return engine

        except OperationalError as e:
            if attempt == retries - 1:
                logger.error(f"Failed to connect to database after {retries} attempts")
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
    user_id = Column(BigInteger, index=True, nullable=True)
    username = Column(String, nullable=True)
    points = Column(Integer, default=0)

class Admins(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, index=True)
    user_id = Column(BigInteger, index=True)

# Create tables only if they don't exist
Base.metadata.create_all(bind=engine, checkfirst=True)

@contextmanager
def get_db():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database transaction failed: {repr(e)}")
        db.rollback()
        raise
    finally:
        db.close()

class Database:
    def __init__(self):
        """Initialize database connection"""
        Base.metadata.create_all(bind=engine, checkfirst=True)

    def clear_all_points(self, chat_id: int):
        """Clear all points from the specific chat"""
        with get_db() as db:
            db.query(UserPoints).filter(UserPoints.chat_id == chat_id).update({"points": 0})

    def get_user_id_by_username(self, chat_id: int, username: str) -> int:
        """Get user_id by username for specific chat"""
        with get_db() as db:
            user = db.query(UserPoints.user_id).filter(
                UserPoints.chat_id == chat_id,
                UserPoints.username == username
            ).first()
            return user.user_id if user else None

    def get_all_users(self, chat_id: int) -> list:
        """Get list of all usernames in specific chat"""
        with get_db() as db:
            users = db.query(UserPoints.username).filter(
                UserPoints.chat_id == chat_id
            ).all()
            return [user.username for user in users]

    def add_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        """Add points to a user in specific chat"""
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
            logger.error(f"Error in add_points: {repr(e)}")
            return False

    def subtract_points(self, chat_id: int, user_id: int, points: int, username: str = None) -> bool:
        """Subtract points from a user in specific chat"""
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
            logger.error(f"Error in subtract_points: {repr(e)}")
            return False

    def get_user_points(self, chat_id: int, user_id: int = None) -> int:
        """Get points for a specific user in specific chat"""
        try:
            with get_db() as db:
                points = db.query(UserPoints.points).filter(
                    UserPoints.chat_id == chat_id,
                    UserPoints.user_id == user_id
                ).scalar()
                return points or 0
        except Exception as e:
            logger.error(f"Error in get_user_points: {repr(e)}")
            return 0

    def get_top_users(self, chat_id: int, limit: int = 10) -> list:
        """Get top users by points in specific chat"""
        try:
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

                return [(user.user_id, {
                    "points": user.points,
                    "username": user.username
                }) for user in users]
        except Exception as e:
            logger.error(f"Error in get_top_users: {repr(e)}")
            return []

    def add_admin(self, chat_id: int, user_id: int):
        """Add an admin to the database"""
        with get_db() as db:
            admin = db.query(Admins).filter(
                Admins.chat_id == chat_id,
                Admins.user_id == user_id
            ).first()

            if not admin:
                admin = Admins(chat_id=chat_id, user_id=user_id)
                db.add(admin)

    def is_admin(self, chat_id: int, user_id: int) -> bool:
        """Check if a user is an admin in a specific chat"""
        with get_db() as db:
            admin = db.query(Admins).filter(
                Admins.chat_id == chat_id,
                Admins.user_id == user_id
            ).first()
            return admin is not None

    def delete_chat_data(self, chat_id: int):
        """Delete all data related to a specific chat"""
        with get_db() as db:
            db.query(UserPoints).filter(UserPoints.chat_id == chat_id).delete()
            db.query(Admins).filter(Admins.chat_id == chat_id).delete()

    def get_user_rank(self, chat_id: int, user_id: int = None) -> int:
        """Get the rank of a user in a specific chat"""
        with get_db() as db:
            users = db.query(UserPoints).filter(UserPoints.chat_id == chat_id).order_by(UserPoints.points.desc()).all()
            for rank, user in enumerate(users, 1):
                if user.user_id == user_id:
                    return rank
            return -1