import streamlit as st
import sqlite3
import os
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from io import BytesIO

# ============================================================
# 页面配置 + 隐藏侧边栏
# ============================================================
st.set_page_config(page_title="设备调试预约", page_icon="🔧", layout="wide")

st.markdown(
    """
    <style>
        /* ---------- 隐藏侧边栏 ---------- */
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        footer { visibility: hidden; }

        /* ---------- 全局字体与背景 ---------- */
        html, body, [class*="css"] {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         "PingFang SC", "Microsoft YaHei", sans-serif;
        }
        .block-container {
            padding-top: 2.2rem;
            padding-bottom: 3rem;
            max-width: 1280px;
        }

        /* ---------- 主标题渐变 ---------- */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.1rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
            letter-spacing: 1px;
        }
        .sub-header {
            color: #888;
            font-size: 0.92rem;
            margin-bottom: 1.2rem;
        }

        /* ---------- 按钮统一圆角 ---------- */
        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition: all 0.18s ease;
            border: 1px solid #e0e0e0;
        }
        .stButton > button:hover:not(:disabled) {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.25);
            border-color: #667eea;
        }

        /* ---------- 主操作按钮（渐变） ---------- */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
        }
        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 6px 18px rgba(102,126,234,0.4);
        }

        /* ---------- 表格卡片化 ---------- */
        div[data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #eee;
            box-shadow: 0 2px 10px rgba(0,0,0,0.04);
        }

        /* ---------- 输入框圆角 ---------- */
        .stTextInput input {
            border-radius: 10px !important;
        }

        /* ---------- 分隔线更柔和 ---------- */
        hr {
            border: none;
            border-top: 1px solid #f0f0f0;
            margin: 1.4rem 0;
        }

        /* ---------- 提示条样式 ---------- */
        div[data-testid="stAlert"] {
            border-radius: 10px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">🔧 设备调试时间预约</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">选择合适的时间段，填写工号与姓名即可完成预约</div>',
    unsafe_allow_html=True,
)

# ============================================================
# 时区
# ============================================================
TZ = ZoneInfo("Asia/Hong_Kong")


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 配置区
# ============================================================
TIME_SLOTS = [
    "11:00-12:00",
    "14:00-15:00",
    "15:00-16:00",
    "16:00-17:00",
    "17:00-18:00",
    "18:00-19:00",
]

START_DATE = date(2026, 10, 30)
EXCLUDE_DATES = {date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)}
TARGET_DAYS = 4
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def get_available_dates():
    dates = []
    d = START_DATE
    while len(dates) < TARGET_DAYS:
        if d.weekday() < 5 and d not in EXCLUDE_DATES:
            dates.append(d)
        d += timedelta(days=1)
    return dates


AVAILABLE_DATES = get_available_dates()

try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except Exception:
    ADMIN_PASSWORD = "admin123"

# ============================================================
# 数据库
# ============================================================
_here = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(_here) == "pages":
    _here = os.path.dirname(_here)
DB_DIR = os.path.join(_here, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "equipment_reservations.db")


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            employee_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL UNIQUE,
            date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(date, time_slot)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date_slot ON reservations(date, time_slot)")
    conn.commit()
    conn.close()


def get_all_reservations():
    """返回 {(date_str, time_slot): employee_id}"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute("SELECT date, time_slot, employee_id FROM reservations")
    data = {(d, ts): eid for d, ts, eid in cur.fetchall()}
    conn.close()
    return data


def get_all_reservations_detail():
    """返回 {(date_str, time_slot): {'employee_id':..., 'name':...}} —— 用于总览表显示姓名+工号"""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute(
        """SELECT r.date, r.time_slot, r.employee_id, e.name
           FROM reservations r
           JOIN employees e ON r.employee_id = e.employee_id"""
    )
    data = {
        (d, ts): {"employee_id": eid, "name": nm}
        for d, ts, eid, nm in cur.fetchall()
    }
    conn.close()
    return data


def reserve(employee_id, name, date_str, time_slot):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cur = conn.execute(
            "SELECT COUNT(*) FROM reservations WHERE date = ? AND time_slot = ?",
            (date_str, time_slot),
        )
        if cur.fetchone()[0] > 0:
            conn.execute("ROLLBACK")
            return False, "slot_taken"

        cur = conn.execute(
            "SELECT COUNT(*) FROM reservations WHERE employee_id = ?", (employee_id,)
        )
        if cur.fetchone()[0] > 0:
            conn.execute("ROLLBACK")
            return False, "already_reserved"

        cur = conn.execute(
            "SELECT name FROM employees WHERE employee_id = ?", (employee_id,)
        )
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO employees (employee_id, name, created_at) VALUES (?, ?, ?)",
                (employee_id, name, now_str()),
            )

        conn.execute(
            "INSERT INTO reservations (employee_id, date, time_slot, created_at) "
            "VALUES (?, ?, ?, ?)",
            (employee_id, date_str, time_slot, now_str()),
        )
        conn.execute("COMMIT")
        return True, "ok"
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def get_my_reservation(employee_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute(
        """SELECT r.date, r.time_slot, r.created_at, e.name
           FROM reservations r
           JOIN employees e ON r.employee_id = e.employee_id
           WHERE r.employee_id = ?""",
        (employee_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def cancel_reservation(employee_id):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "SELECT date, time_slot FROM reservations WHERE employee_id = ?",
            (employee_id,),
        )
        row = cur.fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return False, None, None
        conn.execute("DELETE FROM reservations WHERE employee_id = ?", (employee_id,))
        conn.execute("COMMIT")
        return True, row[0], row[1]
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def get_all_reservations_df():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    df = pd.read_sql_query(
        """SELECT e.employee_id AS 工号, e.name AS 姓名,
                  r.date AS 日期, r.time_slot AS 时间段, r.created_at AS 预约时间
           FROM reservations r
           JOIN employees e ON r.employee_id = e.employee_id
           ORDER BY r.date, r.time_slot""",
        conn,
    )
    conn.close()
    return df


init_db()

# ============================================================
# session_state
# ============================================================
if "page" not in st.session_state:
    st.session_state.page = "预约"
if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False
if "my_employee_id" not in st.session_state:
    st.session_state.my_employee_id = None


# ============================================================
# 预约弹窗
# ============================================================
@st.dialog("填写预约信息")
def reservation_dialog(date_str, slot):
    weekday = WEEKDAY_CN[datetime.strptime(date_str, "%Y-%m-%d").weekday()]

    st.markdown(
        f"""
        <div style="background:linear-gradient(135deg,#eef1ff 0%,#f6f0ff 100%);
                    padding:16px 20px;border-radius:12px;margin-bottom:16px;
                    border-left:5px solid #667eea;">
            <div style="font-size:13px;color:#777;">您选择的时间段</div>
            <div style="font-size:19px;font-weight:700;color:#333;margin-top:2px;">
                {date_str}（{weekday}）
            </div>
            <div style="font-size:17px;font-weight:700;color:#667eea;margin-top:2px;">
                {slot}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    employee_id = st.text_input("工号", max_chars=30, key="dlg_eid", placeholder="请输入工号")
    name = st.text_input("姓名", max_chars=30, key="dlg_name", placeholder="请输入姓名")

    st.caption("📌 每个工号仅可预约一个时间段。")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ 确认预约", type="primary", use_container_width=True):
            eid = employee_id.strip()
            nm = name.strip()
            if not eid:
                st.warning("⚠️ 请填写工号")
            elif not nm:
                st.warning("⚠️ 请填写姓名")
            else:
                try:
                    ok, status = reserve(eid, nm, date_str, slot)
                    if ok:
                        st.session_state.my_employee_id = eid
                        st.session_state["reserve_result"] = {
                            "ok": True,
                            "date": date_str,
                            "slot": slot,
                            "name": nm,
                        }
                        st.session_state.pop("dialog_slot", None)
                        st.rerun()
                    else:
                        if status == "slot_taken":
                            st.error("❌ 该时段刚被他人预约，请选择其他时段。")
                        elif status == "already_reserved":
                            st.error(
                                "❌ 该工号已预约过其他时段。"
                                "请先在页面「我的预约」中取消后再约。"
                            )
                except Exception as e:
                    st.error(f"系统错误：{e}")
    with c2:
        if st.button("取消", use_container_width=True):
            st.session_state.pop("dialog_slot", None)
            st.rerun()


# ============================================================
# 我的预约卡片
# ============================================================
def render_my_reservation_card():
    eid = st.session_state.my_employee_id
    if not eid:
        return

    row = get_my_reservation(eid)
    if row is None:
        st.session_state.my_employee_id = None
        return

    d_str, slot, created_at, name = row
    weekday = WEEKDAY_CN[datetime.strptime(d_str, "%Y-%m-%d").weekday()]

    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#e8f5e9 0%,#f1f8e9 100%);
                        border-left:5px solid #2e7d32;
                        padding:16px 20px;border-radius:12px;
                        box-shadow:0 2px 10px rgba(46,125,50,0.10);">
                <div style="font-size:13px;color:#555;font-weight:600;">✅ 我的预约</div>
                <div style="font-size:17px;font-weight:700;margin-top:6px;color:#1b5e20;">
                    {name}（工号：{eid}）
                </div>
                <div style="font-size:16px;font-weight:700;color:#2e7d32;margin-top:4px;">
                    {d_str}（{weekday}）　{slot}
                </div>
                <div style="font-size:12px;color:#777;margin-top:6px;">
                    预约时间：{created_at}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.write("")
        st.write("")
        if st.button("取消预约", key="cancel_my_btn", use_container_width=True):
            ok, c_date, c_slot = cancel_reservation(eid)
            if ok:
                st.session_state.my_employee_id = None
                st.success(f"✅ 已取消 **{c_date} {c_slot}** 的预约。")
                st.rerun()
            else:
                st.error("取消失败，请重试。")


# ============================================================
# 预约网格（美化版）
# ============================================================
def render_grid(reservations):
    n_dates = len(AVAILABLE_DATES)
    col_weights = [1.3] + [1] * n_dates

    # 表头
    header_cols = st.columns(col_weights)
    with header_cols[0]:
        st.markdown(
            """
            <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                        color:#fff;padding:10px;border-radius:10px;
                        text-align:center;font-weight:700;font-size:14px;">
                时间段
            </div>
            """,
            unsafe_allow_html=True,
        )
    for i, d in enumerate(AVAILABLE_DATES):
        with header_cols[i + 1]:
            st.markdown(
                f"""
                <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
                            color:#fff;padding:10px;border-radius:10px;text-align:center;">
                    <div style="font-weight:700;font-size:14px;">{d.strftime('%m-%d')}</div>
                    <div style="font-size:12px;opacity:0.9;">{WEEKDAY_CN[d.weekday()]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # 数据行
    for slot in TIME_SLOTS:
        row_cols = st.columns(col_weights)

        with row_cols[0]:
            st.markdown(
                f"""
                <div style="background:#f7f8fc;border:1px solid #eceef5;
                            padding:12px 8px;border-radius:10px;
                            text-align:center;font-weight:600;font-size:14px;
                            color:#444;height:52px;line-height:28px;">
                    {slot}
                </div>
                """,
                unsafe_allow_html=True,
            )

        for i, d in enumerate(AVAILABLE_DATES):
            date_str = d.strftime("%Y-%m-%d")
            key = (date_str, slot)
            with row_cols[i + 1]:
                if key in reservations:
                    is_mine = (
                        st.session_state.my_employee_id is not None
                        and reservations[key] == st.session_state.my_employee_id
                    )
                    label = "✅ 我的预约" if is_mine else "🔴 已预约"
                    st.button(
                        label,
                        key=f"btn_{date_str}_{slot}",
                        disabled=True,
                        use_container_width=True,
                    )
                else:
                    if st.button(
                        "🟢 可预约",
                        key=f"btn_{date_str}_{slot}",
                        use_container_width=True,
                    ):
                        st.session_state.pop("dlg_eid", None)
                        st.session_state.pop("dlg_name", None)
                        st.session_state["dialog_slot"] = (date_str, slot)
                        st.rerun()


# ============================================================
# 主页面
# ============================================================
def render_reservation_page():
    if "reserve_result" in st.session_state:
        r = st.session_state.pop("reserve_result")
        st.success(f"✅ 预约成功！**{r['date']} {r['slot']}**（{r['name']}）")
        st.balloons()

    render_my_reservation_card()

    st.markdown("### 📅 可预约时段")
    st.caption("🟢 点击空闲格子填写工号和姓名即可预约 ｜ 🔴 已被预约 ｜ ✅ 我的预约")

    reservations = get_all_reservations()
    render_grid(reservations)

    if "dialog_slot" in st.session_state:
        reservation_dialog(*st.session_state["dialog_slot"])

    st.divider()

    with st.expander("🔍 换设备 / 刷新后找回我的预约"):
        st.caption("如果换设备或刷新后看不到「我的预约」，可输入工号找回。")
        qid = st.text_input("工号", max_chars=30, key="query_eid", placeholder="请输入您的工号")
        if st.button("查询", key="query_btn"):
            q = qid.strip()
            if not q:
                st.warning("⚠️ 请输入工号")
            else:
                row = get_my_reservation(q)
                if row is None:
                    st.info(f"工号 **{q}** 暂无预约记录。")
                else:
                    st.session_state.my_employee_id = q
                    st.success(f"已找回：**{row[3]}**，预约 **{row[0]} {row[1]}**")
                    st.rerun()

    st.divider()
    if st.button("🔐 管理员入口"):
        st.session_state.page = "管理员"
        st.rerun()


# ============================================================
# 管理员页面
# ============================================================
def render_admin_page():
    st.markdown("### 🔐 管理员页面")

    if st.button("← 返回预约页面"):
        st.session_state.page = "预约"
        st.rerun()

    if not st.session_state.admin_authed:
        pwd = st.text_input("请输入管理员密码", type="password", key="admin_pwd_input")
        if st.button("登录", type="primary"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authed = True
                st.rerun()
            else:
                st.error("❌ 密码错误")
        return

    st.success("✅ 已登录管理员")
    if st.button("退出登录"):
        st.session_state.admin_authed = False
        st.rerun()

    st.divider()

    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown("### 📋 全部预约记录")
    with c2:
        if st.button("🔄 刷新数据", use_container_width=True, type="primary"):
            st.rerun()

    st.caption(f"最后刷新时间：{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")

    df = get_all_reservations_df()

    if df.empty:
        st.info("暂无预约记录。")
        return

    total_slots = len(AVAILABLE_DATES) * len(TIME_SLOTS)
    st.caption(
        f"共 **{len(df)}** 条预约，**{df['工号'].nunique()}** 位预约人；"
        f"总时段 **{total_slots}** 个，剩余 **{total_slots - len(df)}** 个"
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    # ---------- 时段总览（含姓名 + 工号） ----------
    st.markdown("### 📊 时段总览（姓名 + 工号）")
    detail = get_all_reservations_detail()

    matrix_rows = []
    for d in AVAILABLE_DATES:
        date_str = d.strftime("%Y-%m-%d")
        row = {"日期": f"{date_str}（{WEEKDAY_CN[d.weekday()]}）"}
        for slot in TIME_SLOTS:
            key = (date_str, slot)
            if key in detail:
                nm = detail[key]["name"]
                eid = detail[key]["employee_id"]
                row[slot] = f"{nm}（{eid}）"
            else:
                row[slot] = "空闲"
        matrix_rows.append(row)
    matrix_df = pd.DataFrame(matrix_rows)
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)

    # ---------- 导出 Excel ----------
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="预约明细")
        matrix_df.to_excel(writer, index=False, sheet_name="时段总览")
    output.seek(0)
    timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 下载预约表 (Excel，含明细和时段总览)",
        data=output,
        file_name=f"设备调试预约表_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    st.markdown("### 📈 按日期统计")
    stat = df.groupby("日期").size().reset_index(name="已约数")
    stat["总时段"] = len(TIME_SLOTS)
    stat["剩余"] = stat["总时段"] - stat["已约数"]
    st.dataframe(stat, use_container_width=True, hide_index=True)


# ============================================================
# 渲染路由
# ============================================================
if st.session_state.page == "管理员":
    render_admin_page()
else:
    render_reservation_page()

st.divider()
st.caption(
    "📌 说明：每个工号仅可预约一个时间段；时段被预约后其他人无法再选；"
    "可在「我的预约」中取消后重新选择。"
)
