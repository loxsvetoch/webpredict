from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import hash_password

register_router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@register_router.get("/register")
def register_get(request: Request):
    flash = request.session.pop("flash", [])
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "flash": flash,
            "active_page": "reg"
        }
    )

@register_router.post("/register")
def register_post(
    request: Request,
    last_name: str = Form(...),
    first_name: str = Form(...),
    patronymic: str = Form(...),
    phone_number: str = Form(...),
    psw: str = Form(...),
    psw_again: str = Form(...),
    db: Session = Depends(get_db)
):
    # проверка совпадения паролей
    if psw != psw_again:
        request.session.setdefault("flash", []).append(("error", "Пароли не совпадают."))
        return RedirectResponse(url="/register", status_code=303)

    # проверка уникальности телефона
    if db.query(User).filter(User.phone_number == phone_number).first():
        request.session.setdefault("flash", []).append(("error", "Телефон уже зарегистрирован."))
        return RedirectResponse(url="/register", status_code=303)

    # создание пользователя
    user = User(
        last_name=last_name,
        first_name=first_name,
        patronymic=patronymic,
        phone_number=phone_number,
        password=hash_password(psw)
    )
    db.add(user)
    db.commit()
    
    request.session.setdefault("flash", []).append(("success", "Регистрация прошла успешно!"))
    return RedirectResponse(url="/login", status_code=303)