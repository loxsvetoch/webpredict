# routers/uploads.py

import csv
from pathlib import Path
from typing import List

from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import JSONResponse
from jose import ExpiredSignatureError
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User, Teacher, Subject, Group, Exam
from auth import decode_access_token

router_upload = APIRouter()
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Не авторизован")
    try:
        data = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(401, "Сессия истекла")
    except Exception:
        raise HTTPException(401, "Неверный токен")
    user = db.get(User, data.get("user_id"))
    if not user:
        raise HTTPException(401, "Пользователь не найден")
    return user


@router_upload.post("/upload-csv-multiple")
async def upload_csv_multiple(
    file_types: List[str] = Form(...),
    files: List[UploadFile] = File(...),
    user: User = Depends(get_current_user),
):
    if len(file_types) != len(files):
        raise HTTPException(400, "Количество типов и файлов не совпадает")
    for ftype, upload in zip(file_types, files):
        target = UPLOAD_DIR / f"{ftype}.csv"
        data = await upload.read()
        target.write_bytes(data)
    return {"message": "Файлы загружены"}


@router_upload.post("/process-uploads")
async def process_uploads(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    errors: List[str] = []
    exam_inserted = 0
    exam_skipped = 0

    # --- 1) group.csv ---
    p = UPLOAD_DIR / "group.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                raw = (row.get("id") or "").strip()
                if not raw or raw.upper() == "NULL":
                    continue
                try:
                    gid = int(raw)
                except ValueError:
                    continue
                if not db.query(Group).filter_by(id=gid, user_id=user.id).first():
                    title = row.get("title", "").strip()
                    try:
                        sy = int(row.get("start_year") or 0)
                    except ValueError:
                        sy = 0
                    db.add(Group(id=gid, user_id=user.id, title=title, start_year=sy))
    else:
        errors.append("group.csv не найден")

    # --- 2) subject.csv ---
    p = UPLOAD_DIR / "subject.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                raw = (row.get("id") or "").strip()
                if not raw or raw.upper() == "NULL":
                    continue
                try:
                    sid = int(raw)
                except ValueError:
                    continue
                if not db.query(Subject).filter_by(id=sid, user_id=user.id).first():
                    title = row.get("title", "").strip()
                    db.add(Subject(id=sid, user_id=user.id, title=title, short_title=title))
    else:
        errors.append("subject.csv не найден")

    # --- 3) teacher.csv ---
    p = UPLOAD_DIR / "teacher.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f), start=1):
                raw = (row.get("id") or row.get("teacher_id") or "").strip()
                if not raw or raw.upper() == "NULL":
                    continue
                try:
                    tid = int(raw)
                except ValueError:
                    continue
                if not db.query(Teacher).filter_by(id=tid, user_id=user.id).first():
                    fn = row.get("firstname", "").strip()
                    ln = row.get("lastname", "").strip()
                    pt = row.get("patronymic", "").strip()
                    db.add(Teacher(id=tid, user_id=user.id,
                                   first_name=fn, last_name=ln, patronymic=pt))
    else:
        errors.append("teacher.csv не найден")

    # Сбрасываем на БД, чтобы дальше можно было запросить ID-списки
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        errors.append(f"Ошибка при flush(): {e}")
        return JSONResponse(status_code=500, content={"errors": errors})

    # Подготовим списки валидных ID для FK
    valid_group_ids   = {g.id for g in db.query(Group.id).filter_by(user_id=user.id)}
    valid_subject_ids = {s.id for s in db.query(Subject.id).filter_by(user_id=user.id)}
    valid_teacher_ids = {t.id for t in db.query(Teacher.id).filter_by(user_id=user.id)}

    # --- 4) exam.csv ---
    p = UPLOAD_DIR / "exam.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected = {"academic_group_id", "teacher_id", "subject_id",
                        "session_number", "exam_number", "success_count", "all_count"}
            missing = expected - set(reader.fieldnames or [])
            if missing:
                errors.append(f"exam.csv: пропущены колонки {missing}")
            else:
                for i, row in enumerate(reader, start=1):
                    raw = {k: (row.get(k) or "").strip() for k in expected}
                    # пропуск NULL/пустых
                    if any(v.upper() == "NULL" or not v for v in raw.values()):
                        exam_skipped += 1
                        continue
                    try:
                        gid = int(raw["academic_group_id"])
                        tid = int(raw["teacher_id"])
                        sid = int(raw["subject_id"])
                        ses = int(raw["session_number"])
                        num = int(raw["exam_number"])
                        suc = int(raw["success_count"])
                        allc = int(raw["all_count"])
                    except ValueError:
                        errors.append(f"exam.csv, строка {i}: неверный формат числа")
                        exam_skipped += 1
                        continue

                    # проверка на вхождение в только что добавленные
                    if gid not in valid_group_ids or \
                       tid not in valid_teacher_ids or \
                       sid not in valid_subject_ids:
                        exam_skipped += 1
                        continue

                    db.add(Exam(
                        academic_group_id=gid,
                        teacher_id=tid,
                        subject_id=sid,
                        user_id=user.id,
                        session_number=ses,
                        exam_number=num,
                        success_count=suc,
                        all_count=allc
                    ))
                    exam_inserted += 1
    else:
        errors.append("exam.csv не найден")

    # финальный commit
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        errors.append(f"Ошибка при сохранении в БД: {e}")

    # результат
    status = {"inserted_exams": exam_inserted, "skipped_exams": exam_skipped}
    if errors:
        return JSONResponse(status_code=207, content={"errors": errors, **status})
    return {"message": "Данные успешно импортированы", **status}
