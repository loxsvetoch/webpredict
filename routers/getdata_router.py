# routers/getdata_router.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Group, Teacher, Subject, User
from auth import decode_access_token
from fastapi import Request, HTTPException
from jose import ExpiredSignatureError

getdata_router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Не авторизован")
    try:
        data = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(401, "Сессия истекла")
    except Exception:
        raise HTTPException(401, "Неверный токен")
    user = db.get(User, data["user_id"])
    if not user:
        raise HTTPException(401, "Пользователь не найден")
    return user

@getdata_router.get("/groups")
def list_groups(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [
        {"id": g.id, "title": g.title}
        for g in db.query(Group).filter(Group.user_id == user.id).all()
    ]

@getdata_router.get("/teachers")
def list_teachers(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [
        {"id": t.id, "full_name": f"{t.last_name} {t.first_name} {t.patronymic}"}
        for t in db.query(Teacher).filter(Teacher.user_id == user.id).all()
    ]

@getdata_router.get("/subjects")
def list_subjects(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [
        {"id": s.id, "short_title": s.short_title}
        for s in db.query(Subject).filter(Subject.user_id == user.id).all()
    ]
