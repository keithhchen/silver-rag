from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from typing import List, Dict, Optional
from app.models.user import User, UserRole, UserLog
from app.services.user_service import UserService
from app.services.database import DatabaseService
from app.config import Settings
from loguru import logger
from datetime import timedelta, datetime

# JWT Configuration
SECRET_KEY = "your-secret-key"  # In production, this should be in environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Initialize services
settings = Settings()
db_service = DatabaseService(settings)
user_service = UserService(db_service.async_session)

# Define endpoint permissions
ENDPOINT_PERMISSIONS: Dict[str, List[UserRole]] = {
    # "/users/": [UserRole.ADMIN],  # Only admin can create users
    # "/documents/": [UserRole.ADMIN, UserRole.USER],  # Both roles can access documents
}

async def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user(token: str) -> User:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await user_service.get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return User.model_validate(user)

async def get_token_from_header(request: Request) -> Optional[str]:
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.replace("Bearer ", "")

async def log_activity(user_id: int, endpoint: str, method: str, status_code: int):
    try:
        async with db_service.async_session() as session:
            log = UserLog(
                user_id=user_id,
                action=f"{method}_{endpoint}",
                details=f"Accessed {endpoint} with {method}"
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log activity: {str(e)}")

# Utility function for controllers to get current user
async def get_authenticated_user(request: Request) -> Optional[User]:
    token = await get_token_from_header(request)
    if not token:
        return None
        
    payload = await verify_token(token)
    if not payload:
        return None
        
    username = payload.get("sub")
    if not username:
        return None
        
    user_db = await user_service.get_user_by_username(username)
    if not user_db:
        return None
        
    return User(
        id=user_db.id,
        uuid=user_db.uuid,
        username=user_db.username,
        role=user_db.role,
        created_at=user_db.created_at,
        updated_at=user_db.updated_at
    )

class AuthMiddleware:
    async def __call__(self, request: Request, call_next):
        # Get token if provided
        token = await get_token_from_header(request)
        user = None

        if token:
            # Verify token and get user
            payload = await verify_token(token)
            if payload:
                username = payload.get("sub")
                user = await user_service.get_user_by_username(username)

                # Check endpoint permissions only if endpoint is explicitly restricted
                for endpoint, allowed_roles in ENDPOINT_PERMISSIONS.items():
                    if request.url.path.startswith(endpoint):
                        if not user:
                            return JSONResponse(
                                status_code=401,
                                content={"detail": "Authentication required for this endpoint"}
                            )
                        if user.role not in allowed_roles:
                            return JSONResponse(
                                status_code=403,
                                content={"detail": "Not enough permissions"}
                            )

        try:

            # Proceed with the request
            response = await call_next(request)

            # Log the activity only if user is authenticated
            if user:
                await log_activity(
                    user.id,
                    request.url.path,
                    request.method,
                    response.status_code
                )

            return response

        except Exception as e:
            logger.error(f"Middleware error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )