from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import hash_password, verify_password, create_access_token

auth_router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@auth_router.get("/login")
def login_get(request: Request):
    flash = request.session.pop("flash", [])
    return templates.TemplateResponse(
        "login.html", {"request": request, "flash": flash, "active_page": "login"}
    )

@auth_router.post("/login")
def login_post(
    request: Request,
    phone_number: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.phone_number == phone_number).first()
    if not user or not verify_password(password, user.password):
        request.session.setdefault("flash", []).append(("error", "Неверные учетные данные."))
        return RedirectResponse(url="/login", status_code=303)
    
    token = create_access_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie("access_token", token, httponly=True)
    request.session.setdefault("flash", []).append(("success", f"Добро пожаловать, {user.first_name}!"))
    return response

@auth_router.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("access_token")
    request.session.setdefault("flash", []).append(("success", "Вы вышли из системы."))
    return response