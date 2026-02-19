from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import auth, repository
from app.dependencies import get_connection

from .schemas import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, connection=Depends(get_connection)) -> TokenResponse:
    user = repository.get_user_by_username(connection, request.username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    verified, replacement_hash = auth.verify_and_update_password(
        request.password, user.hashed_password
    )
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if replacement_hash is not None:
        repository.update_user_password(
            connection,
            user_id=user.id,
            hashed_password=replacement_hash,
        )
    token = auth.create_access_token(connection, user.id)
    return TokenResponse(access_token=token)
