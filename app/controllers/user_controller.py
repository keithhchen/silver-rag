from fastapi import APIRouter, HTTPException, Request, Depends
from app.middleware.auth import JWTBearer
from loguru import logger
from pydantic import BaseModel
from app.models.user import UserCreate, User, UserUpdate
from app.exceptions import DatabaseError
from app.services.user_service import UserService
from app.services.database import DatabaseService
from app.config import Settings

router = APIRouter()
settings = Settings()
db_service = DatabaseService(settings)
user_service = UserService(db_service.async_session)

@router.post("/create", response_model=User)
async def create_user(user_data: UserCreate):
    try:
        result = await user_service.create_user(user_data)
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(login_data: LoginRequest):
    try:
        result = await user_service.login_user(login_data.username, login_data.password)
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.put("/change-password")
async def change_password(username: str, password_update: UserUpdate):
    try:
        result = await user_service.change_user_password(username, password_update)
        return result
    except DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/profile", dependencies=[Depends(JWTBearer())])
async def get_profile(request: Request):
    try:
        # Access the authenticated user profile from request state
        user_profile = request.state.user
        return user_profile
    except DatabaseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")