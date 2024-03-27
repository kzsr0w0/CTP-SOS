####################################################
#
# streamlitの全部のせ
#
#
######################################################

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import calendar
import pulp
from datetime import datetime as dt 


st.title('来店人数予測アプリ')

# ユーザーからの日付入力を受け取る
selected_date = st.date_input('予測したい日付を選択してください。')

# 入力部分
# 年と月の情報入手
selected_year = selected_date.year
selected_month = selected_date.month
# 月の日数を取得
days_in_month = calendar.monthrange(selected_year, selected_month)[1]

Max_Staff = []

# --- スタッフの詳細設定のためのサイドバー --- #
# スタッフの詳細設定のためのサイドバー
st.sidebar.title("スタッフ設定")

# スタッフ名と希望休
STAFF_COUNT = st.sidebar.number_input('スタッフの人数', min_value=1, value=5)

staff_names = []
staff_off_requests = {}

# 全員が休みの日を選択
all_off_days = st.sidebar.multiselect('全員休みの日を選択', list(range(1, days_in_month + 1)), key='all_off')


for i in range(STAFF_COUNT):
    # 各スタッフ名の入力
    default_staff_name = f'Staff{i + 1}'
    name = st.sidebar.text_input(f'スタッフ名 {i + 1}', value=default_staff_name, key=f'name_{i}')
    staff_names.append(name)
    
    # 各スタッフの希望休を入力
    off_days = st.sidebar.multiselect(f'{name}希望休', list(range(1, days_in_month + 1)), key=f'off_{i}')
    staff_off_requests[name] = off_days




if st.button('予測とシフト作成'):
    # FastAPIエンドポイントにリクエストを送信
    response = requests.post(
        'http://localhost:8000/predict_day/', 
        json={
            'year': selected_date.year,
            'month': selected_date.month,
            'day': selected_date.day
        }
    )

    if response.status_code == 200:
        result = response.json()
        predictions = result.get('predictions', [])
        if predictions:  # 予測結果がある場合
            # 予測結果を表で表示
            df_predictions = pd.DataFrame({'Hour': range(24), 'Predicted': predictions}).set_index('Hour').T
            st.write(f"予測日: {result.get('date', 'Unknown')}")
            st.dataframe(df_predictions)  # Streamlitで表を表示
            # グラフで予測結果を表示
            fig = px.bar(df_predictions.T.reset_index(), x='Hour', y='Predicted', labels={'Predicted': '予測来場者数'}, title=f"{result.get('date', 'Unknown')} の来店人数の予測")
            st.plotly_chart(fig)
            # 最大必要人数の推定と必要スタッフ数の計算
            Max_num = int(max(predictions))
            st.write('最大来場者数：', Max_num)
            Max_Staff = Max_num // 400  # 1人の1時間当たりの処理人数が400人設定
            st.write('必要なスタッフ数：', Max_Staff)
        else:
            st.write("予測結果がありません。")
    else:
        st.write('予測に失敗しました。')


##############################################################
#   シフト作成
#
#
#
############################################

# --- Streamlitの設定 ----------------------------------------------------------------------------------- #
# タイトル
st.title('シフト作成')



# 月の各日とその曜日を組み合わせたリストを作成
dates_and_weekdays = [
    (day, calendar.day_name[dt(selected_year, selected_month, day).weekday()])
    for day in range(1, days_in_month + 1)
]

# 曜日ごとの必要スタッフ人数
needed_staff_per_day = {
    'Monday': Max_Staff,
    'Tuesday': Max_Staff,
    'Wednesday': Max_Staff,
    'Thursday': Max_Staff,
    'Friday': Max_Staff,
    'Saturday': Max_Staff,
    'Sunday': Max_Staff
}

print



# --- 最適化 --------------------------------------------------------------------------------------------- #
#   仕様
#   - 31日分
#   - 従業員は1カ月に取得しなければいけない休日数が8日とする
#   - 希望休は基本叶える
#   - 日曜休みの店舗とする
#
#   制約条件
#   - 最小休日数が8日
#   - 各営業日における出勤者数を7名～8名で割り当てる
#   - 従業員の希望休を反映する
#   - 5連勤を作らない (隣り合う5マスの合計が1以上)
#
# -------------------------------------------------------------------------------------------------------- #

# --- 定数の定義 --- #
# 必要休暇数
H_req = {e: 8 for e in staff_names}  # 従業員は1カ月に取得しなければいけない休日数が8日


# モデルの定義
problem = pulp.LpProblem("ShiftScheduling", pulp.LpMinimize)

# 変数の定義
# 変数の定義
shifts = {(staff, day): pulp.LpVariable(f"shift_{staff}_{day}", 0, 1, pulp.LpBinary)
          for staff in range(STAFF_COUNT) for day in range(1, days_in_month + 1)}


# --- 制約の追加 --- #
# 各日に対して、必要なスタッフ数を担保する制約を追加
for day, weekday in dates_and_weekdays:  # 日付と曜日の組み合わせ
    required_staff = needed_staff_per_day[weekday]  # その曜日に必要なスタッフ数
    # その日に対する必要スタッフ数の制約を追加
    problem += pulp.lpSum(shifts[staff, day] for staff in range(STAFF_COUNT)) >= required_staff

    # すべてのスタッフが休む日に対する特別な処理
    if day in all_off_days:
        for staff in range(STAFF_COUNT):
            problem += shifts[staff, day] == 0  # この日は全員が休み
    else:
        # 全員が休む日を除外して、通常の必要スタッフ数を確保
        problem += pulp.lpSum(shifts[staff, day] for staff in range(STAFF_COUNT)) >= required_staff

# その他のスタッフ関連の制約
for staff in range(STAFF_COUNT):
    # 必要な最小休日数を担保
    problem += pulp.lpSum(shifts[staff, day] for day in range(1, days_in_month + 1)) <= days_in_month - 8

    # 希望休の考慮
    for day in staff_off_requests[staff_names[staff]]:
        problem += shifts[staff, day] == 1

    # 5連勤を防ぐ
    for day in range(1, days_in_month - 4):
        problem += shifts[staff, day] + shifts[staff, day + 1] + shifts[staff, day + 2] + shifts[staff, day + 3] + shifts[staff, day + 4] <= 4



# --- 目的関数（ここではダミー）--- #
problem += 0


# --- ソルバーの実行 --- #
problem.solve()


# --- 結果の取得とデータフレームの作成 ------------------------------------------------------------------------- #
# 結果の取得とデータフレームの作成
# スケジュールデータの準備
schedule_data = [] 
for staff, staff_name in enumerate(staff_names):
    for day, weekday in dates_and_weekdays:
        if day in staff_off_requests[staff_name]:  # 希望休の日
            schedule_data.append({'Staff': staff_name, 'Date': f'{day} ({weekday})', 'Shift': '希'})
        elif pulp.value(shifts[staff, day]) == 1:  # 出勤
            schedule_data.append({'Staff': staff_name, 'Date': f'{day} ({weekday})', 'Shift': '〇'})
        else:  # 休み
            schedule_data.append({'Staff': staff_name, 'Date': f'{day} ({weekday})', 'Shift': '―'})

df_schedule = pd.DataFrame(schedule_data)

# 結果をデータフレームに変換し、ピボット
df_schedule['Date'] = pd.Categorical(df_schedule['Date'], categories=[f'{day} ({weekday})' for day, weekday in dates_and_weekdays], ordered=True)
schedule_df = df_schedule.pivot_table(index='Staff', columns='Date', values='Shift', aggfunc='first', fill_value='―')

# スケジュールの表示
st.title('Monthly Shift Schedule')
st.write("Here is the monthly shift schedule with requested off days and weekdays:")
st.table(schedule_df)