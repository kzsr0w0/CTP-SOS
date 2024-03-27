import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import LabelEncoder
from statsmodels.tsa.arima.model import ARIMA
from pmdarima import auto_arima
import matplotlib.pyplot as plt

# CSVファイルからデータを読み込む
data = pd.read_csv('/content/peopleflow_202204.csv')

# 不要な列の除外
data = data.drop(['date', 'camera_id', 'Gender'], axis=1)

# 年齢列の除外
data = data.drop(['Age00','Age10','Age20','Age30','Age40','Age50','Age60','Age70','NaN'],axis=1)

# Outputの除外
data = data.drop('Output', axis=1)

# 年、月、日、時間でグループ化し、Inputを集計
data = data.groupby(['year', 'month', 'day', 'hour'])['Input'].sum().reset_index()

# 曜日の生成
# 日付型の列を作成
data['date'] = pd.to_datetime(data[['year', 'month', 'day']])

# 曜日を抽出し、新しい列として追加
data['weekday'] = data['date'].dt.day_name()
data = data.drop('date', axis=1)

# 曜日の数値化
# LabelEncoderのインスタンス化
encoder = LabelEncoder()
# ラベルエンコーダーを曜日データにフィットさせる
encoder.fit(data['weekday'])
# 曜日データをエンコード（変換）する
data['weekday'] = encoder.transform(data['weekday'])

# 'Input' 列を使ってARIMAモデルを適用
# ARIMAモデルのパラメータを自動的に選択
auto_model = auto_arima(data['Input'], seasonal=True, m=24, trace=True, error_action='ignore', suppress_warnings=True)
auto_model.summary()

# ARIMAモデルの訓練（自動選択されたパラメータを使用）
model = ARIMA(data['Input'], order=auto_model.order, seasonal_order=auto_model.seasonal_order)
fitted = model.fit()



import pickle

# モデルをファイルに保存
with open('model_arima_20240314.pkl', 'wb') as pkl:
    pickle.dump(fitted, pkl)