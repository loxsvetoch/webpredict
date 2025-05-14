from io import BytesIO
from scipy import stats
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
class DataHandler():
    """
    Класс хранения, обработки и визуализации данных
    """
    def __init__(self, path="uploads/exam.csv"):
        # Чтение данных
        g = pd.read_csv(path)
        self._groups = g.copy()
        
        # Количество неуспевших: разница между общим количеством и количеством успешных
        self._groups["students_failed"] = self._groups["all_count"] - self._groups["success_count"]
        # Доля неуспевших
        self._groups["group_performance"] = self._groups["students_failed"] / self._groups["all_count"]
        
        # Сортировка и добавление exam_index
        self._groups = self._groups.sort_values(by=["session_number", "exam_number"]).reset_index(drop=True)
        self._groups["exam_index"] = np.arange(1, len(self._groups) + 1)

        # Расчет взвешенных норм
        self.calc_ex_weigh_norm()
        self.calc_sub_weighted_norm()
        
    def get_data_statistics(self) -> dict:
        stats = {
            "num_rows": int(self._groups.shape[0]),
            "num_columns": int(self._groups.shape[1]),
            "column_info": {}
        }        
        for col in self._groups.columns:
            col_info = {
                "dtype": str(self._groups[col].dtype),
                "num_missing": int(self._groups[col].isna().sum()),
            }            
            if self._groups[col].dtype in ["int64", "float64"]:
                col_info.update({
                    "mean": float(self._groups[col].mean()),
                    "std": float(self._groups[col].std()),
                    "min": float(self._groups[col].min()),
                    "max": float(self._groups[col].max()),
                    "median": float(self._groups[col].median())
                })
            elif self._groups[col].dtype == "object":
                col_info["num_unique"] = int(self._groups[col].nunique())
                mode = self._groups[col].mode()
                col_info["most_common"] = str(mode[0]) if not mode.empty else None            
            stats["column_info"][col] = col_info        
        return stats
    
    @property
    def groups(self):
        return self._groups.copy()

    def calc_ex_weigh_norm(self):
        """
        Расчет взвешенной нормы для экзаменаторов и добавление её в self._groups
        """
        grouped_examiners = self._groups.groupby("teacher_id").agg({
            'students_failed': 'sum',
            'all_count': 'sum'
        }).reset_index()
        grouped_examiners['examiner_weighted_norm'] = grouped_examiners['students_failed'] / grouped_examiners['all_count']
        self._groups = pd.merge(self._groups,
                                grouped_examiners[["teacher_id", "examiner_weighted_norm"]],
                                on="teacher_id",
                                how="left")

    def calc_sub_weighted_norm(self):
        """
        Расчет взвешенной нормы для предметов и добавление её в self._groups
        """
        grouped_subject = self._groups.groupby("subject_id").agg({
            'students_failed': 'sum',
            'all_count': 'sum'
        }).reset_index()
        grouped_subject['subject_weighted_norm'] = grouped_subject['students_failed'] / grouped_subject['all_count']
        self._groups = pd.merge(self._groups,
                                grouped_subject[["subject_id", 'subject_weighted_norm']],
                                on="subject_id",
                                how="left")

class Model():
    """
    Класс реализация модели прогноза
    """
    def __init__(self, data_handler, decay=0.9, alpha=0.05):   
        self.data = data_handler.groups  # Данные всех групп
        self.decay = decay
        self.alpha = alpha
        self.all = 0
        self.neadekv = 0

    def calculate_group(self, group_data: pd.DataFrame):
        df = group_data.sort_values('exam_index').copy()
        max_session = df['session_number'].max()
        w = np.array(self.decay ** (max_session - df['session_number']))
        
        T = df['examiner_weighted_norm'] * df['subject_weighted_norm']
        S = df['subject_weighted_norm']
        y = df['group_performance']

        A = np.sum(w * T * T)
        B = np.sum(w * S * T)
        C = np.sum(w * y * T)
        D = np.sum(w * S * S)
        E = np.sum(w * y * S)

        det = A * D - B * B
        if det != 0:
            a = (C * D - B * E) / det
            b = (A * E - B * C) / det
        else:
            a, b = 0.0, 0.0

        # Инициализируем t_a и t_b как np.nan заранее
        t_a = np.nan
        t_b = np.nan

        if len(df) > 2 and det != 0:
            yp_initial = a * T + b * S
            rss = np.sum(w * (y - yp_initial)**2)
            sigma2 = rss / (len(df) - 2)
            se_a = np.sqrt(sigma2 * D / det) if D != 0 else np.nan
            se_b = np.sqrt(sigma2 * A / det) if A != 0 else np.nan

            # Теперь безопасно вычисляем t_a и t_b
            if se_a and se_a != 0:
                t_a = a / se_a
            if se_b and se_b != 0:
                t_b = b / se_b

            t_crit = stats.t.ppf(1 - self.alpha / 2, len(df) - 2)

            # Обнуляем коэффициенты, если они незначимы
            if not np.isnan(t_a) and abs(t_a) < t_crit:
                a = 0.0
            if not np.isnan(t_b) and abs(t_b) < t_crit:
                b = 0.0

            # Пересчитываем yp и error после обнуления
            yp = a * T + b * S
            resid = y - yp
            error = np.abs(resid)
        else:
            # Если группа слишком мала или матрица вырожденная
            yp = np.zeros_like(y)
            resid = y - yp
            error = np.abs(resid)
            a, b = 0.0, 0.0
            se_a = se_b = np.nan
            t_a = t_b = np.nan

        # Ограничиваем прогноз в [0, 1]
        df['yp'] = np.clip(a * T + b * S, 0, 1)
        df['error'] = error  # Теперь error = |y - clipped_yp|
        df['a'] = a
        df['b'] = b
        df['t_a'] = t_a
        df['t_b'] = t_b

        return df
    
    def calculate_all(self, target_groups=None):
        """
        Расчет регрессии отдельно для каждой группы.
        Сохраняет данные в файл `debug_groups.txt` только для групп с ≥8 экзаменами.
        """
        if target_groups is None:
            target_groups = [301601, -145860, 143649]
        debug_file = 'debug_groups.txt'

        # Очистка файла перед началом
        if os.path.exists(debug_file):
            os.remove(debug_file)

        results = []
        for group_id, group_data in self.data.groupby("academic_group_id"):
            df = self.calculate_group(group_data)

            # Исключаем группы с менее чем 8 экзаменами после обработки
            if len(df) < 8:
                print(f"Группа {group_id}: (len {len(df)}  < 8)")
                continue

            results.append(df)

            # Логирование удалённых экзаменов
            num_exams_before = len(group_data)
            num_exams_after = len(df)
            removed_count = num_exams_before - num_exams_after

            # Сохранение данных для целевых групп
            if group_id in target_groups:
                df_debug = df.copy()
                df_debug['group_id'] = group_id
                df_debug.to_csv(debug_file, mode='a', sep='\t',
                                header=not os.path.exists(debug_file), index=False)

        return pd.concat(results, ignore_index=True)

    def detect_outliers(self, results: pd.DataFrame, percentile: float = 0.9):
        """
        Выявление 10% экзаменов с наибольшими ошибками внутри каждой группы
        """
        to_remove = []
        for group_id, group_df in results.groupby("academic_group_id"):
            threshold = group_df["error"].quantile(percentile)
            outliers = group_df[group_df["error"] >= threshold].index.tolist()
            to_remove.extend(outliers)
        return to_remove
    
    def recalculate_with_outliers_removed(self, results: pd.DataFrame):
        """
        Удаление 10% худших экзаменов и пересчет модели
        """
        target_groups = [301601, -145860, 143649]  # Целевые группы
        debug_file = "debug_groups.txt"

        # Удаление выбросов
        outliers = self.detect_outliers(results)
        filtered_data = self.data.drop(index=outliers).reset_index(drop=True)
        self.data = filtered_data

        # Пересчёт модели после удаления
        final_results = self.calculate_all(target_groups=target_groups)

        # Сохранение в debug_groups.txt ПОСЛЕ удаления выбросов и пересчёта
        for group_id, group_df in final_results.groupby("academic_group_id"):
            if group_id in target_groups:
                df_debug = group_df.copy()
                df_debug['group_id'] = group_id
                df_debug.to_csv(debug_file, mode='a', sep='\t',
                                header=not os.path.exists(debug_file), index=False)

        return final_results

    def forecast(self, group_id: int, teacher_id: int, subject_id: int, exam_index: int):
        """
        Прогнозирование доли неуспевающих для будущего экзамена
        """
        hist = self.data[
            (self.data['academic_group_id'] == group_id) &
            (self.data['exam_index'] < exam_index)
        ]
        if len(hist) < 3:
            raise ValueError("Недостаточно предыдущих экзаменов для прогноза")

        df_hist = self.calculate_group(hist)
        a = df_hist['a'].iloc[-1]
        b = df_hist['b'].iloc[-1]
        norm_t = self.data.loc[self.data['teacher_id'] == teacher_id, 'examiner_weighted_norm'].iloc[0]
        norm_s = self.data.loc[self.data['subject_id'] == subject_id, 'subject_weighted_norm'].iloc[0]

        T = norm_t * norm_s
        S = norm_s
        return float(np.clip(a * T + b * S, 0, 1))