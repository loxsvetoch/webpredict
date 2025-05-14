# routers/forecast_router.py

import uuid
from typing import Any
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from predict import DataHandler, Model
import pandas as pd

forecast_router = APIRouter()

# Для сессии пользователя (не используем сам handler, но нужна сессия)
handlers: dict[str, DataHandler] = {}

async def get_data_handler(request: Request) -> DataHandler:
    session_id = request.session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["session_id"] = session_id
    if session_id not in handlers:
        handlers[session_id] = DataHandler(path="uploads/exam.csv")
    return handlers[session_id]

@forecast_router.get(
    "/forecast/{group_id}/{teacher_id}/{subject_id}/{exam_index}"
)
async def get_forecast(
    request: Request,
    group_id: int,
    teacher_id: int,
    subject_id: int,
    exam_index: int,
    handler: DataHandler = Depends(get_data_handler)
):
    """
    Логика прогноза, независимая от handler.calculate_all:
      - берём все строки uploads/exam.csv
      - фильтруем по group_id
      - сортируем по session_number, exam_number
      - проверяем, что записей >=3 и exam_index > существующих
      - строим модель по истории, берём последние a, b
      - берём нормы examiner_weighted_norm, subject_weighted_norm из handler
      - считаем прогноз и возвращаем
    """
    try:
        # Читаем свежие данные
        dh = DataHandler(path="uploads/exam.csv")
        df = dh.groups  # pandas.DataFrame
        
        # Фильтруем только по этой группе
        grp = df[df["academic_group_id"] == group_id].copy()
        # Сортируем точно так же, как в DataHandler
        grp = grp.sort_values(["session_number", "exam_number"]).reset_index(drop=True)
        
        if len(grp) < 3:
            raise ValueError("Недостаточно предыдущих экзаменов для прогноза")

        # Проверяем, что пользователь запросил future-index > текущего count
        if exam_index <= len(grp):
            raise ValueError(f"Этот экзамен уже есть (текущих: {len(grp)}). Введите номер > {len(grp)}")

        # Построим регрессию на всей истории
        model = Model(dh, decay=0.9, alpha=0.1)
        hist_df = model.calculate_group(grp)
        # Последняя строка содержит наши скорректированные a,b
        a = hist_df["a"].iloc[-1]
        b = hist_df["b"].iloc[-1]

        # Получим нормы по преподавателю и предмету из исходного датасета
        # (уже посчитанные в DataHandler.__init__)
        norm_t = dh.groups.loc[
            dh.groups["teacher_id"] == teacher_id, "examiner_weighted_norm"
        ]
        norm_s = dh.groups.loc[
            dh.groups["subject_id"] == subject_id, "subject_weighted_norm"
        ]
        if norm_t.empty or norm_s.empty:
            raise ValueError("Не найдены нормы для указанного преподавателя или предмета")
        norm_t = norm_t.iloc[0]
        norm_s = norm_s.iloc[0]

        # Считаем прогноз
        y_p = a * norm_t * norm_s + b * norm_s
        y_p = float(max(0.0, min(1.0, y_p)))  # clip [0,1]

        return {"forecast": y_p}

    except ValueError as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    except Exception as e:
        # для отладки можно раскомментировать:
        # return JSONResponse(status_code=500, content={"detail": str(e)})
        return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка"})
