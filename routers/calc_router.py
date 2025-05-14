import uuid
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from io import BytesIO

import matplotlib
matplotlib.use('Agg')  # безголовый бэкенд
import matplotlib.pyplot as plt

import base64
import numpy as np
from scipy.interpolate import make_interp_spline
from starlette.concurrency import run_in_threadpool

from schemas import Group as GroupSchema
from predict import DataHandler, Model

calc_router = APIRouter()
handlers: dict[str, DataHandler] = {}


async def get_data_handler(request: Request) -> DataHandler:
    session_id = request.session.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['session_id'] = session_id
    if session_id not in handlers:
        handlers[session_id] = DataHandler()
    return handlers[session_id]

# Internal sync function for heavy computation
def _calculate(handler: DataHandler) -> list[GroupSchema]:
    model = Model(handler, decay=0.9, alpha=0.1)
    df = model.calculate_all()
    df1 = model.recalculate_with_outliers_removed(df)
    df2 = model.recalculate_with_outliers_removed(df1)

    result: list[GroupSchema] = []
    for gid, group_df in df2.groupby('academic_group_id'):
        # compute error and parameters
        error = group_df['error'].abs().mean()
        row = group_df.iloc[0]
        t_a, a, b = row['t_a'], row['a'], row['b']
        exam_nums = np.arange(1, len(group_df) + 1)
        # plot
        fig, ax = plt.subplots(figsize=(6,4))
        try:
            x_smooth = np.linspace(exam_nums.min(), exam_nums.max(), 300)
            spl_act = make_interp_spline(exam_nums, group_df['group_performance'], k=3)
            spl_pred = make_interp_spline(exam_nums, group_df['yp'], k=3)
            ax.plot(x_smooth, spl_act(x_smooth), label='Реальные')
            ax.plot(x_smooth, spl_pred(x_smooth), label='Предсказанные')
        except ValueError:
            ax.plot(exam_nums, group_df['group_performance'], marker='o', label='Реальные', color="green")
            ax.plot(exam_nums, group_df['yp'], marker='o', label='Предсказанные')
        ax.set_xlabel('Экзамены')
        ax.set_ylabel('Успеваемость')
        ax.set_title(f'Группа {gid}')
        ax.legend()
        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode()
        result.append(GroupSchema(
            id=int(gid),
            error=str(error),
            t_a=str(t_a),
            a=str(a),
            b=str(b),
            img=img_b64,
        ))
    return result

def _forecast(handler: DataHandler, group_id, teacher_id, subject_id, exam_index):
    model = Model(handler, decay=0.9, alpha=0.1)
    df = model.calculate_all()
    df1 = model.recalculate_with_outliers_removed(df)
    predict = model.forecast(group_id, teacher_id, subject_id, exam_index)
    return predict

    
@calc_router.get('/calculate_all')  # remove response_model to avoid Pydantic error
async def calculate_all(
    background_tasks: BackgroundTasks,
    handler: DataHandler = Depends(get_data_handler)
):
    # Run computation in threadpool to avoid blocking
    groups = await run_in_threadpool(_calculate, handler)
    return groups

@calc_router.get('/get_data_stats')
async def get_data_stats(handler: DataHandler = Depends(get_data_handler)):
    stats = await run_in_threadpool(handler.get_data_statistics)
    return JSONResponse(content=stats)
