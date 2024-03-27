###########################################################
#   CTP-SOS 1  来客予測
#
#   
###########################################################
from fastapi import FastAPI
import pickle
import numpy as np
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()

# モデルの読み込み
with open('model_arima_20240314.pkl', 'rb') as pkl:
    model = pickle.load(pkl)

# 基準日の設定
start_date = datetime(2022, 4, 30) # 学習させたデータが4/30まで


# エンコーダの設定
class PredictDayRequest(BaseModel):
    year: int
    month: int
    day: int

@app.post("/predict_day/")
async def predict_day(request: PredictDayRequest):
    # 正確な日付を設定
    selected_date = datetime(request.year, request.month, request.day)
    response_date = selected_date.strftime('%Y-%m-%d')
    # 日数の差を計算
    delta = selected_date - start_date
    days_passed = delta.days

    # ARIMAモデルから予測を取得
    forecast_results = model.get_forecast(steps=days_passed * 24)
        ### ここなに！？↓
    predictions = forecast_results.predicted_mean.tolist()
    # 予測結果から後ろから25個分のデータのみを選択
    latest_predictions = predictions[-24:]
    
    return {"date": response_date, "predictions": latest_predictions}
