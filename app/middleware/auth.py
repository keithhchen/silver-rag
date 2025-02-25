from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.user_service import UserService
from app.services.database import DatabaseService
from app.config import Settings
from typing import Optional
import jwt

settings = Settings()
db_service = DatabaseService(settings)
user_service = UserService(db_service.async_session)

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        
        if not credentials:
            raise HTTPException(status_code=401, detail="Invalid authorization code.")

        if not credentials.scheme.lower() == "bearer":
            raise HTTPException(status_code=401, detail="Invalid authentication scheme.")

        try:
            # Verify the JWT token
            payload = jwt.decode(
                credentials.credentials,
                user_service.secret_key,
                algorithms=[user_service.algorithm]
            )
            
            # Get user profile using the token
            user_profile = await user_service.get_user_profile_from_token(credentials.credentials)
            
            # Attach the user profile to the request state
            request.state.user = user_profile
            
            return credentials.credentials

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
        except Exception as e:
            raise HTTPException(status_code=401, detail="Could not validate credentials")