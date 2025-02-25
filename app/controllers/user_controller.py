from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from loguru import logger
from pydantic import BaseModel
from app.models.user import UserCreate, User, UserUpdate, UserRole
from app.exceptions import DatabaseError
from app.services.user_service import UserService
from app.services.database import DatabaseService
from app.config import Settings
from app.middleware import auth_middleware

router = APIRouter()
settings = Settings()
db_service = DatabaseService(settings)
user_service = UserService(db_service.async_session)

from app.middleware.auth_middleware import SECRET_KEY, ALGORITHM, create_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    return await auth_middleware.get_current_user(token)

@router.post("/", response_model=User)
async def create_user(user_data: UserCreate):
    try:
        user = await user_service.create_user(user_data)
        return user
    except DatabaseError as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=503, detail="Internal server error")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(login_data: LoginRequest):
    try:
        user = await user_service.authenticate_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Incorrect username or password"
            )

        access_token = create_access_token(
            data={"sub": user.username}
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": user.username,
            "uuid": user.uuid
        }

    except DatabaseError as e:
        logger.error(f"Database error during login: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/change-password")
async def change_password(password_update: UserUpdate, token: str = Depends(oauth2_scheme)):
    try:
        # Validate token and get user
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = await user_service.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        success = await user_service.update_password(user.id, password_update)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update password")

        return {"message": "Password updated successfully"}

    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")
    except DatabaseError as e:
        logger.error(f"Database error during password change: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during password change: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_user)):
    try:
        if not current_user:
            raise HTTPException(status_code=400, detail="Not logged in")

        return {
            "uuid": current_user.uuid,
            "username": current_user.username,
            "role": current_user.role,
            "created_at": current_user.created_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error while getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    try:
        # Validate token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        # In a real-world application, you might want to add the token to a blacklist
        # or implement a token revocation mechanism here

        return {"message": "Successfully logged out"}

    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid token")
    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")