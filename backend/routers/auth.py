import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.jwt_handler import create_token, verify_password, get_current_user
from db.connection import fetch_one

logger = logging.getLogger("routers.auth")

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    # 1. Check admins table first
    admin = await fetch_one(
        """
        SELECT admin_id, full_name, email, password_hash
        FROM admins
        WHERE email = $1 AND is_active = TRUE
        """,
        body.email,
    )
    if admin and verify_password(body.password, admin["password_hash"]):
        token = create_token({
            "sub": admin["admin_id"],
            "role": "admin",
            "email": admin["email"],
            "full_name": admin["full_name"],
        })
        logger.info(f"Admin login: {admin['email']} ({admin['admin_id']})")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": admin["admin_id"],
            "role": "admin",
            "full_name": admin["full_name"],
            "email": admin["email"],
        }

    # 2. Fall back to customers table
    customer = await fetch_one(
        """
        SELECT customer_id, email, password_hash,
               first_name || ' ' || last_name AS full_name
        FROM customers
        WHERE email = $1 AND is_active = TRUE
        """,
        body.email,
    )
    if customer and verify_password(body.password, customer["password_hash"]):
        token = create_token({
            "sub": customer["customer_id"],
            "role": "customer",
            "email": customer["email"],
            "full_name": customer["full_name"],
        })
        logger.info(f"Customer login: {customer['email']} ({customer['customer_id']})")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user_id": customer["customer_id"],
            "role": "customer",
            "full_name": customer["full_name"],
            "email": customer["email"],
        }

    # 3. Neither matched
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    # JWT is stateless — token invalidation is handled client-side
    return {"message": "Logged out successfully"}
