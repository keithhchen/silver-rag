from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt
from app.models.user import UserDB, UserCreate, User, UserUpdate, UserLog, UserRole
from app.exceptions import DatabaseError
from loguru import logger
import jwt

class UserService:
    def __init__(self, async_session: sessionmaker):
        self.async_session = async_session
        self.secret_key = "your-secret-key"  # In production, this should be in environment variables
        self.algorithm = "HS256"

    def _hash_password(self, password: str) -> str:
        return bcrypt.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.verify(plain_password, hashed_password)

    def _create_token(self, user_uuid: str, role: str) -> str:
        expire = datetime.utcnow() + timedelta(days=7)
        to_encode = {
            "sub": str(user_uuid),
            "role": role,
            "exp": expire
        }
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

    async def authenticate_user(self, username: str, password: str) -> User:
        try:
            user = await self.get_user_by_username(username)
            if not user or not self._verify_password(password, user.password_hash):
                raise DatabaseError("Incorrect username or password")
            return User.model_validate({
                "id": user.id,
                "uuid": user.uuid,
                "username": user.username,
                "role": user.role,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            })
        except DatabaseError as e:
            raise e
        except Exception as e:
            raise DatabaseError(f"Failed to authenticate user: {str(e)}")

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


    async def log_activity(self, user_id: int, action: str, details: str) -> None:
        """Unified method for logging user activities."""
        try:
            async with self.async_session() as session:
                log = UserLog(
                    user_id=user_id,
                    action=action,
                    details=details
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to log user activity: {str(e)}")
            raise DatabaseError(f"Failed to log user activity: {str(e)}")

    async def login_user(self, username: str, password: str) -> dict:
        """Handle user login and return formatted response with JWT token."""
        try:
            user = await self.authenticate_user(username, password)
            if not user:
                raise DatabaseError("Incorrect username or password")

            token = self._create_token(user.uuid, user.role)

            return {
                "uuid": user.uuid,
                "username": user.username,
                "role": user.role,
                "created_at": user.created_at,
                "token": token
            }
        except Exception as e:
            raise DatabaseError(f"Failed to login user: {str(e)}")

    async def get_user_profile(self, username: str) -> dict:
        """Get user profile information."""
        try:
            user = await self.get_user_by_username(username)
            if not user:
                raise DatabaseError("User not found")

            return {
                "uuid": user.uuid,
                "username": user.username,
                "role": user.role,
                "created_at": user.created_at
            }
        except Exception as e:
            raise DatabaseError(f"Failed to get user profile: {str(e)}")

    async def change_user_password(self, username: str, password_update: UserUpdate) -> dict:
        """Handle password change and return response."""
        try:
            user = await self.get_user_by_username(username)
            if not user:
                raise DatabaseError("User not found")

            success = await self.update_password(user.id, password_update)
            if not success:
                raise DatabaseError("Failed to update password")

            return {"message": "Password updated successfully"}
        except Exception as e:
            raise DatabaseError(f"Failed to change password: {str(e)}")

    async def get_user_profile_from_token(self, token: str) -> dict:
        """Get user profile information from JWT bearer token."""
        try:
            # Decode and validate the token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_uuid = payload.get('sub')
            
            # Get user from database using UUID
            async with self.async_session() as session:
                query = select(UserDB).where(UserDB.uuid == user_uuid)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if not user:
                    raise DatabaseError("User not found")
                
                return {
                    "uuid": user.uuid,
                    "username": user.username,
                    "role": user.role,
                    "created_at": user.created_at
                }
        except jwt.ExpiredSignatureError:
            raise DatabaseError("Token has expired")
        except jwt.InvalidTokenError:
            raise DatabaseError("Invalid token")
        except Exception as e:
            raise DatabaseError(f"Failed to get user profile from token: {str(e)}")