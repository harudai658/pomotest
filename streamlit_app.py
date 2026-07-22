# -*- coding: utf-8 -*-
"""
学習計画・実行・振り返りアプリ
--------------------------------
計画 → 実行 → 記録 → 振り返り → 改善 の学習サイクルを支援する
Streamlit製・単一ファイルのアプリです。

■ 実行方法
    pip install streamlit pandas plotly
    streamlit run study_app.py

■ データ保存について
    SQLite（study_app.db）にローカル保存しますが、Streamlitの実行環境によっては
    再起動等でデータが失われる可能性があります。重要な記録はCSV/コピー/
    スクリーンショットで別途保存してください（アプリ内でも案内します）。
"""

import random
import sqlite3
import string
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ============================================================
# 定数
# ============================================================
DB_PATH = "study_app.db"

SUBJECTS = ["数学", "英語", "国語", "理科", "社会", "プログラミング", "探究", "その他"]
PRIORITIES = ["高", "中", "低"]
PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2}
ACHIEVEMENTS = ["達成", "部分達成", "未達成"]
UNDONE_REASONS = ["時間不足", "難しかった", "集中できなかった", "計画時間が短かった", "その他"]

PERSISTENCE_NOTICE = (
    "このアプリはログイン不要で利用できます。\n\n"
    "ただし、Streamlitの仕様上、データの永続保存を完全に保証するものではありません。\n"
    "以下の場合、データが失われる可能性があります。\n"
    "- アプリが再起動された場合\n"
    "- サーバー側のデータがリセットされた場合\n"
    "- ブラウザ環境が変わった場合\n"
    "- 保存情報が削除された場合\n\n"
    "重要な学習記録は以下の方法で保存してください。\n"
    "- スクリーンショット保存\n"
    "- CSVダウンロード\n"
    "- テキストコピー"
)

st.set_page_config(page_title="学習コーチングアプリ", page_icon="📚", layout="wide")


# ============================================================
# DB
# ============================================================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            created_date TEXT,
            subject TEXT,
            task TEXT,
            priority TEXT,
            target_minutes INTEGER,
            theme TEXT,
            question TEXT,
            research_content TEXT,
            reference_material TEXT,
            next_action TEXT,
            completed INTEGER DEFAULT 0,
            plan_date TEXT,
            assigned_today INTEGER DEFAULT 0,
            postponed INTEGER DEFAULT 0
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            task_id INTEGER,
            record_date TEXT,
            subject TEXT,
            task TEXT,
            planned_minutes INTEGER,
            actual_minutes INTEGER,
            achievement TEXT,
            comment TEXT,
            good_points TEXT,
            improvements TEXT,
            next_memo TEXT,
            reason TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def generate_user_id() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def add_task(user_id, subject, task, priority, target_minutes,
             theme="", question="", research_content="", reference_material="", next_action=""):
    conn = get_conn()
    conn.execute(
        """INSERT INTO tasks
        (user_id, created_date, subject, task, priority, target_minutes,
         theme, question, research_content, reference_material, next_action)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, str(datetime.now().date()), subject, task, priority, target_minutes,
         theme, question, research_content, reference_material, next_action),
    )
    conn.commit()
    conn.close()


def get_uncompleted_tasks(user_id):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM tasks WHERE user_id=? AND completed=0 ORDER BY id", conn, params=(user_id,)
    )
    conn.close()
    return df


def delete_task(task_id):
    conn = get_conn()
    conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def clear_today_plan(user_id, today):
    conn = get_conn()
    conn.execute(
        "UPDATE tasks SET assigned_today=0, postponed=0, plan_date=NULL "
        "WHERE user_id=? AND plan_date=? AND completed=0",
        (user_id, today),
    )
    conn.commit()
    conn.close()


def create_today_plan(user_id, today, budget_minutes):
    clear_today_plan(user_id, today)
    df = get_uncompleted_tasks(user_id)
    df = df.sort_values(by="priority", key=lambda s: s.map(PRIORITY_ORDER))

    conn = get_conn()
    c = conn.cursor()
    total = 0
    for _, row in df.iterrows():
        minutes = row["target_minutes"] or 0
        if total + minutes <= budget_minutes:
            total += minutes
            c.execute(
                "UPDATE tasks SET plan_date=?, assigned_today=1, postponed=0 WHERE id=?",
                (today, row["id"]),
            )
        else:
            c.execute(
                "UPDATE tasks SET plan_date=?, assigned_today=0, postponed=1 WHERE id=?",
                (today, row["id"]),
            )
    conn.commit()
    conn.close()


def get_today_plan(user_id, today, assigned=True):
    conn = get_conn()
    flag_col = "assigned_today" if assigned else "postponed"
    df = pd.read_sql_query(
        f"SELECT * FROM tasks WHERE user_id=? AND plan_date=? AND {flag_col}=1 AND completed=0 "
        "ORDER BY CASE priority WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, id",
        conn, params=(user_id, today),
    )
    conn.close()
    return df


def mark_task_completed(task_id):
    conn = get_conn()
    conn.execute("UPDATE tasks SET completed=1 WHERE id=?", (task_id,))
    conn.commit()
    conn.close()


def save_record(user_id, task_id, record_date, subject, task, planned_minutes, actual_minutes,
                 achievement, comment, good_points, improvements, next_memo, reason):
    conn = get_conn()
    conn.execute(
        """INSERT INTO records
        (user_id, task_id, record_date, subject, task, planned_minutes, actual_minutes,
         achievement, comment, good_points, improvements, next_memo, reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, task_id, record_date, subject, task, planned_minutes, actual_minutes,
         achievement, comment, good_points, improvements, next_memo, reason),
    )
    conn.commit()
    conn.close()


def get_records(user_id, record_date=None):
    conn = get_conn()
    if record_date:
        df = pd.read_sql_query(
            "SELECT * FROM records WHERE user_id=? AND record_date=? ORDER BY id",
            conn, params=(user_id, record_date),
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM records WHERE user_id=? ORDER BY id DESC", conn, params=(user_id,)
        )
    conn.close()
    return df


init_db()

# ============================================================
# セッション状態の初期化
# ============================================================
defaults = {
    "user_id": None,
    "timer_task_id": None,
    "timer_start": None,
    "timer_elapsed_before": 0.0,  # 分単位
    "timer_running": False,
    "show_finish_form": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

TODAY = str(datetime.now().date())


def elapsed_minutes_now():
    e = st.session_state.timer_elapsed_before
    if st.session_state.timer_running and st.session_state.timer_start:
        e += (datetime.now() - st.session_state.timer_start).total_seconds() / 60
    return e


# ============================================================
# サイドバー：匿名ID管理
# ============================================================
st.sidebar.title("📚 学習コーチングアプリ")

if st.session_state.user_id is None:
    st.sidebar.info(PERSISTENCE_NOTICE)
    st.sidebar.subheader("学習IDの発行・入力")
    mode = st.sidebar.radio("利用方法を選んでください", ["新しい学習IDを発行する", "既存の学習IDを入力する"])

    if mode == "新しい学習IDを発行する":
        if st.sidebar.button("学習IDを発行する"):
            st.session_state.user_id = generate_user_id()
            st.rerun()
    else:
        input_id = st.sidebar.text_input("学習ID（例：A72K9F）").strip().upper()
        if st.sidebar.button("このIDで開始する"):
            if input_id:
                st.session_state.user_id = input_id
                st.rerun()
            else:
                st.sidebar.warning("学習IDを入力してください。")

    st.title("📚 学習コーチングアプリへようこそ")
    st.write("左のサイドバーから学習IDを発行、または既存のIDを入力して開始してください。")
    st.warning(PERSISTENCE_NOTICE)
    st.stop()

else:
    st.sidebar.success("学習ID")
    st.sidebar.code(st.session_state.user_id)
    st.sidebar.caption("このIDをスクリーンショット・コピー・メモで保存してください。")
    with st.sidebar.expander("⚠️ データ保存についての注意"):
        st.write(PERSISTENCE_NOTICE)
    if st.sidebar.button("別の学習IDに切り替える"):
        st.session_state.user_id = None
        st.session_state.timer_task_id = None
        st.rerun()

USER_ID = st.session_state.user_id

# ============================================================
# ヘッダー：現在時刻
# ============================================================
header_l, header_r = st.columns([3, 1])
with header_l:
    st.title("📚 学習コーチングアプリ")
with header_r:
    st.metric("現在時刻", datetime.now().strftime("%H:%M"))

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📝 学習内容登録", "📅 今日の計画", "⏱️ 学習実行", "📊 振り返り・記録", "💾 保存・データ管理"]
)

# ============================================================
# タブ1：学習内容登録
# ============================================================
with tab1:
    st.header("学習内容登録")
    with st.form("add_task_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            subject = st.selectbox("教科", SUBJECTS)
            priority = st.selectbox("優先順位", PRIORITIES)
        with col2:
            task_name = st.text_input("やること（例：二次関数の問題演習）")
            target_minutes = st.number_input("目標時間（分）", min_value=5, max_value=600, value=30, step=5)

        theme = question = research_content = reference_material = next_action = ""
        if subject == "探究":
            st.markdown("**探究用追加項目（任意）**")
            theme = st.text_input("探究テーマ")
            question = st.text_input("課題・問い")
            research_content = st.text_area("調査内容")
            reference_material = st.text_input("参考資料")
            next_action = st.text_input("次回やること")

        submitted = st.form_submit_button("登録する")
        if submitted:
            if not task_name.strip():
                st.warning("「やること」を入力してください。")
            else:
                add_task(USER_ID, subject, task_name.strip(), priority, int(target_minutes),
                         theme, question, research_content, reference_material, next_action)
                st.success("学習内容を登録しました。")

    st.subheader("登録済み・未完了の学習内容")
    df_tasks = get_uncompleted_tasks(USER_ID)
    if df_tasks.empty:
        st.caption("まだ学習内容が登録されていません。")
    else:
        for _, row in df_tasks.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.write(f"**{row['subject']}** ｜ {row['task']}")
                    if row["subject"] == "探究" and row["theme"]:
                        st.caption(f"テーマ：{row['theme']}")
                with c2:
                    st.write(f"優先度：{row['priority']}")
                with c3:
                    st.write(f"{row['target_minutes']}分")
                if st.button("削除", key=f"del_{row['id']}"):
                    delete_task(row["id"])
                    st.rerun()

# ============================================================
# タブ2：今日の計画
# ============================================================
with tab2:
    st.header("今日の学習計画作成")
    budget = st.number_input("今日の勉強時間（分）", min_value=10, max_value=1000, value=120, step=10)

    if st.button("計画を作成する", type="primary"):
        create_today_plan(USER_ID, TODAY, int(budget))
        st.toast("計画を作成しました。")
        st.info(PERSISTENCE_NOTICE)

    st.subheader("今日やること")
    plan_df = get_today_plan(USER_ID, TODAY, assigned=True)
    if plan_df.empty:
        st.caption("まだ今日の計画がありません。上のボタンから作成してください。")
    else:
        for i, row in enumerate(plan_df.itertuples(), start=1):
            st.write(
                f"{i}. **{row.subject}**｜{row.task}｜優先度：{row.priority}｜予定時間：{row.target_minutes}分"
            )

    postponed_df = get_today_plan(USER_ID, TODAY, assigned=False)
    if not postponed_df.empty:
        st.subheader("後でやる学習")
        for row in postponed_df.itertuples():
            st.write(f"- {row.subject}｜{row.task}｜優先度：{row.priority}｜{row.target_minutes}分")

# ============================================================
# タブ3：学習実行
# ============================================================
with tab3:
    st.header("学習実行")
    st.caption(f"現在時刻：{datetime.now().strftime('%H:%M')}（表示を更新するには下のボタンを押してください）")

    todo_df = get_today_plan(USER_ID, TODAY, assigned=True)

    if todo_df.empty:
        st.info("実行できるタスクがありません。先に「今日の計画」タブで計画を作成してください。")
    else:
        options = {f"{r.subject}｜{r.task}（{r.target_minutes}分）": r.id for r in todo_df.itertuples()}
        selected_label = st.selectbox("タスクを選択", list(options.keys()))
        selected_id = options[selected_label]
        selected_row = todo_df[todo_df["id"] == selected_id].iloc[0]

        # タスクを切り替えたらタイマーをリセット
        if st.session_state.timer_task_id not in (None, selected_id) and not st.session_state.show_finish_form:
            st.session_state.timer_task_id = None
            st.session_state.timer_running = False
            st.session_state.timer_elapsed_before = 0.0

        st.markdown(f"**教科：** {selected_row['subject']}　**やること：** {selected_row['task']}")
        st.markdown(f"**予定時間：** {selected_row['target_minutes']}分")

        colA, colB, colC, colD = st.columns(4)
        with colA:
            if st.button("▶ スタート", disabled=st.session_state.timer_task_id == selected_id and st.session_state.timer_running):
                st.session_state.timer_task_id = selected_id
                st.session_state.timer_start = datetime.now()
                st.session_state.timer_elapsed_before = 0.0
                st.session_state.timer_running = True
                st.session_state.show_finish_form = False
                st.rerun()
        with colB:
            if st.button("⏸ 一時停止", disabled=not (st.session_state.timer_task_id == selected_id and st.session_state.timer_running)):
                st.session_state.timer_elapsed_before = elapsed_minutes_now()
                st.session_state.timer_running = False
                st.rerun()
        with colC:
            if st.button("▶ 再開", disabled=not (st.session_state.timer_task_id == selected_id and not st.session_state.timer_running and st.session_state.timer_start)):
                st.session_state.timer_start = datetime.now()
                st.session_state.timer_running = True
                st.rerun()
        with colD:
            if st.button("⏹ 終了する", disabled=st.session_state.timer_task_id != selected_id or st.session_state.timer_start is None):
                st.session_state.timer_elapsed_before = elapsed_minutes_now()
                st.session_state.timer_running = False
                st.session_state.show_finish_form = True
                st.rerun()

        if st.button("🔄 表示を更新"):
            st.rerun()

        if st.session_state.timer_task_id == selected_id and st.session_state.timer_start is not None:
            elapsed = elapsed_minutes_now()
            target = selected_row["target_minutes"] or 0

            if elapsed <= target:
                remaining = max(target - elapsed, 0)
                center_text = f"残り{int(remaining)}分"
                ratio = elapsed / target if target > 0 else 0
                color = "#22c55e" if ratio >= 0.9 else "#3b82f6"  # 緑：達成付近／青：学習中
                values = [elapsed, max(target - elapsed, 0)]
                colors = [color, "#e5e7eb"]
            else:
                over = elapsed - target
                center_text = f"+{int(over)}分\n延長学習中"
                color = "#8b5cf6"  # 紫：延長学習
                values = [1]
                colors = [color]

            fig = go.Figure(
                data=[go.Pie(values=values, hole=0.72, marker=dict(colors=colors),
                             textinfo="none", sort=False, direction="clockwise")]
            )
            fig.update_layout(
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=280,
                annotations=[dict(text=center_text, x=0.5, y=0.5, font_size=20, showarrow=False)],
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"開始時刻：{st.session_state.timer_start.strftime('%H:%M') if st.session_state.timer_running else '一時停止中'}　経過時間：約{int(elapsed)}分")

        # 終了後の実績入力フォーム
        if st.session_state.show_finish_form and st.session_state.timer_task_id == selected_id:
            st.subheader("学習実績の入力")
            default_minutes = int(round(st.session_state.timer_elapsed_before))
            with st.form("finish_form"):
                actual_minutes = st.number_input("実際の学習時間（分）", min_value=0, max_value=1000, value=default_minutes)
                achievement = st.selectbox("達成度", ACHIEVEMENTS)
                comment = st.text_area("振り返りコメント")
                good_points = st.text_area("良かった点")
                improvements = st.text_area("改善点")
                next_memo = st.text_input("次回へのメモ")
                reason = ""
                if achievement != "達成":
                    reason = st.selectbox("未達理由", UNDONE_REASONS)

                if st.form_submit_button("記録を保存する"):
                    save_record(
                        USER_ID, int(selected_id), TODAY, selected_row["subject"], selected_row["task"],
                        int(selected_row["target_minutes"]), int(actual_minutes), achievement,
                        comment, good_points, improvements, next_memo, reason,
                    )
                    mark_task_completed(int(selected_id))
                    st.session_state.timer_task_id = None
                    st.session_state.timer_start = None
                    st.session_state.timer_elapsed_before = 0.0
                    st.session_state.timer_running = False
                    st.session_state.show_finish_form = False
                    st.toast("学習記録を保存しました。")
                    st.success("記録を保存しました。「振り返り・記録」タブで確認できます。")
                    st.info(PERSISTENCE_NOTICE)
                    st.rerun()

# ============================================================
# タブ4：振り返り・記録
# ============================================================
with tab4:
    st.header("計画と結果の比較")
    today_records = get_records(USER_ID, TODAY)
    if today_records.empty:
        st.caption("本日の学習記録はまだありません。")
    else:
        show_cols = today_records.rename(
            columns={
                "subject": "教科", "task": "やること", "planned_minutes": "予定(分)",
                "actual_minutes": "実績(分)", "achievement": "達成度", "comment": "コメント",
            }
        )[["教科", "やること", "予定(分)", "実績(分)", "達成度", "コメント"]]
        st.dataframe(show_cols, use_container_width=True, hide_index=True)

        total_planned = int(today_records["planned_minutes"].sum())
        total_actual = int(today_records["actual_minutes"].sum())
        extra = max(total_actual - total_planned, 0)
        c1, c2, c3 = st.columns(3)
        c1.metric("合計予定時間", f"{total_planned}分")
        c2.metric("合計実績時間", f"{total_actual}分")
        c3.metric("追加学習時間", f"{extra}分")

    st.divider()
    st.header("これまでの学習記録")
    all_records = get_records(USER_ID)
    if all_records.empty:
        st.caption("まだ記録がありません。")
    else:
        for row in all_records.itertuples():
            with st.container(border=True):
                st.write(f"**{row.record_date}｜{row.subject}｜{row.task}**")
                st.write(f"予定：{row.planned_minutes}分　実績：{row.actual_minutes}分　達成度：{row.achievement}")
                if row.comment:
                    st.caption(f"コメント：{row.comment}")
                if row.good_points:
                    st.caption(f"良かった点：{row.good_points}")
                if row.improvements:
                    st.caption(f"改善点：{row.improvements}")
                if row.next_memo:
                    st.caption(f"次回へのメモ：{row.next_memo}")
                if row.reason:
                    st.caption(f"未達理由：{row.reason}")

# ============================================================
# タブ5：保存・データ管理
# ============================================================
with tab5:
    st.header("保存・データ管理")
    st.warning(PERSISTENCE_NOTICE)

    all_records = get_records(USER_ID)
    if all_records.empty:
        st.caption("保存できる学習記録がまだありません。")
    else:
        export_df = all_records.rename(
            columns={
                "record_date": "日付", "subject": "教科", "task": "やること",
                "planned_minutes": "予定時間(分)", "actual_minutes": "実績時間(分)",
                "achievement": "達成度", "comment": "コメント",
            }
        )[["日付", "教科", "やること", "予定時間(分)", "実績時間(分)", "達成度", "コメント"]]

        csv_bytes = export_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 CSVをダウンロード", data=csv_bytes,
            file_name=f"study_records_{USER_ID}.csv", mime="text/csv",
        )

        st.subheader("コピー用テキスト")
        st.caption("下のコードブロック右上のアイコンからコピーできます。")
        st.code(export_df.to_csv(index=False, sep="\t"), language=None)

    st.subheader("スクリーンショット保存のご案内")
    st.info("今日の学習記録を残すため、この画面をスクリーンショットしてください。")