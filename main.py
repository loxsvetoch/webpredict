from fastapi import FastAPI, Request, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from config import templates
from database import engine, Base, SessionLocal
from models import User, Group, Teacher, Subject
from auth import hash_password, verify_password, create_access_token, decode_access_token


# Base.metadata.drop_all(bind=engine)

# Base.metadata.create_all(bind=engine)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="another-secret-key")

# Статика и шаблоны
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

templates = Jinja2Templates(directory="frontend/templates")


# Роутеры
from routers.calc_router import calc_router
from routers.uploads import router_upload
from routers.auth_router import auth_router
from routers.regiser_router import register_router
from routers.getdata_router import getdata_router
from routers.forecast_router import forecast_router
app.include_router(calc_router)
app.include_router(router_upload)
app.include_router(auth_router)
app.include_router(register_router)
app.include_router(getdata_router)
app.include_router(forecast_router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.middleware('http')
async def add_user_to_request(request: Request, call_next):
    request.state.user = None
    token = request.cookies.get('access_token')
    db = None
    try:
        if token:
            data = decode_access_token(token)
            db = SessionLocal()
            user = db.query(User).get(data.get('user_id'))
            request.state.user = user
    except Exception:
        request.state.user = None
    finally:
        if db:
            db.close()
    response = await call_next(request)
    return response

# Публичные страницы
@app.get("/", response_class=HTMLResponse)
async def info(request: Request):
    return RedirectResponse(url="/info", status_code=303)

@app.get("/info", response_class=HTMLResponse)
async def info(request: Request):
    return templates.TemplateResponse("info.html", {"request": request, "active_page": "info"})


@app.get("/upload", response_class=HTMLResponse)
async def predict(request: Request):

    return templates.TemplateResponse("upload.html", {"request": request, "active_page": "upload"})


@app.get("/analysis", response_class=HTMLResponse)
async def upload_page(request: Request):

    return templates.TemplateResponse(
        "analys.html", 
        {"request": request, "active_page": "analysis"}
    )

@app.get("/forecast", response_class=HTMLResponse)
async def predict(request: Request):

    return templates.TemplateResponse(\
        "forecast.html",
        {"request": request, "active_page": "forecast"}
        )


@app.get('/groups')
def list_groups(db: Session = Depends(get_db)):
    items = db.query(Group).all()
    return [{"id": g.id, "title": g.title} for g in items]
# аналогично для teachers и subjects

@app.get("/teachers")
async def list_teachers(db: Session = Depends(get_db)):
    teachers = db.query(Teacher).all()
    return [
        {"id": t.id, "full_name": f"{t.first_name} {t.last_name}"}
        for t in teachers
    ]
@app.get("/subjects")
async def list_subjects(db: Session = Depends(get_db)):
    subjects = db.query(Subject).all()
    return [
        {"id": s.id, "short_title": s.short_title, "title": s.title}
        for s in subjects
    ]