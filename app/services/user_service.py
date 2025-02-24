from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt
from app.models.user import UserDB, UserCreate, User, UserUpdate, UserLog, UserRole
from app.exceptions import DatabaseError
from loguru import logger

class UserService:
    def __init__(self, async_session: sessionmaker):
        self.async_session = async_session

    def _hash_password(self, password: str) -> str:
        return bcrypt.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.verify(plain_password, hashed_password)

    async def create_user(self, user_data: UserCreate, created_by_id: int = None) -> User:
        try:
            # Check if username already exists
            existing_user = await self.get_user_by_username(user_data.username)
            if existing_user:
                raise DatabaseError("Username already exists")

            if not user_data.username or len(user_data.username) < 3:
                raise DatabaseError("Username must be at least 3 characters long")

            if not user_data.password or len(user_data.password) < 6:
                raise DatabaseError("Password must be at least 6 characters long")

            async with self.async_session() as session:
                try:
                    # Create user
                    db_user = UserDB(
                        username=user_data.username,
                        password_hash=self._hash_password(user_data.password),
                        role=user_data.role
                    )
                    session.add(db_user)
                    await session.commit()
                    await session.refresh(db_user)

                    # Log user creation
                    log = UserLog(
                        user_id=created_by_id,
                        action="create_user",
                        details=f"Created user {user_data.username}"
                    )
                    session.add(log)
                    await session.commit()

                    return User.model_validate({
                        "id": db_user.id,
                        "uuid": db_user.uuid,
                        "username": db_user.username,
                        "role": db_user.role,
                        "created_at": db_user.created_at,
                        "updated_at": db_user.updated_at
                    })

                except Exception as db_error:
                    await session.rollback()
                    logger.error(f"Database error during user creation: {str(db_error)}")
                    raise DatabaseError(f"Database error during user creation: {str(db_error)}")

        except DatabaseError as e:
            raise e
        except Exception as e:
            logger.error(f"Unexpected error during user creation: {str(e)}")
            raise DatabaseError(f"Failed to create user: {str(e)}")

    async def get_user_by_username(self, username: str) -> UserDB:
        try:
            async with self.async_session() as session:
                query = select(UserDB).where(UserDB.username == username)
                result = await session.execute(query)
                return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseError(f"Failed to get user: {str(e)}")

    async def authenticate_user(self, username: str, password: str) -> User:
        try:
            user = await self.get_user_by_username(username)
            if not user or not self._verify_password(password, user.password_hash):
                return None
            return User.model_validate({
                "id": user.id,
                "uuid": user.uuid,
                "username": user.username,
                "role": user.role,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            })
        except Exception as e:
            raise DatabaseError(f"Failed to authenticate user: {str(e)}")

    async def update_password(self, user_id: int, password_update: UserUpdate) -> bool:
        try:
            async with self.async_session() as session:
                user = await session.get(UserDB, user_id)
                if not user:
                    return False

                user.password_hash = self._hash_password(password_update.password)
                user.updated_at = datetime.utcnow()

                # Log password update
                log = UserLog(
                    user_id=user_id,
                    action="update_password",
                    details="Password updated"
                )
                session.add(log)

                await session.commit()
                return True

        except Exception as e:
            raise DatabaseError(f"Failed to update password: {str(e)}")

    async def get_user_count(self) -> int:
        try:
            async with self.async_session() as session:
                query = select(UserDB)
                result = await session.execute(query)
                users = result.scalars().all()
                return len(users)
        except Exception as e:
            raise DatabaseError(f"Failed to get user count: {str(e)}")