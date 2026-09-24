import streamlit as st
import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo          # ← 新增
import pandas as pd
from io import BytesIO

# ============================================================
# 页面配置 + 隐藏侧边栏
# ============================================================
st.set_page_config(page_title="参赛报名", page_icon="🏆", layout="wide")

st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏆 参赛项目报名")

# ============================================================
# 配置区
# ============================================================
PROJECTS = [
    "【难度：★★】项目一：电商平台商品信息抓取",
    "【难度：★】项目二：天猫红书单品流入流出批量化处理",
    "【难度：★★】项目三：红书抖音本竞单品关键词处理",
    "【难度：★★】项目四：红书抖音反漏斗破圈人群整理及可视化",
    "【难度：★★★】项目五：KOL智能反选全链路执行工具",
    "【难度：★★】项目六：周期报告取数与 Deck 自动化",
    "【难度：★★】项目七：人群画像数据自动化",
    "【难度：★★】项目八：E2E 计算与报告自动化",
    "【难度：★】项目九：Campaign 全周期复盘与知识复用",
]

PROJECT_CATEGORIES = {
    "🎯 生意竞品": PROJECTS[0:3],
    "🎯 人群破圈": PROJECTS[3:4],
    "🎯 KOL 反选": PROJECTS[4:5],
    "🎯 执行赋能": PROJECTS[5:9],
}

MAX_PER_PROJECT = 5
MAX_PER_PERSON = 6

try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except Exception:
    ADMIN_PASSWORD = "admin123"

# ============================================================
# 时区设置
# ============================================================
TZ = ZoneInfo("Asia/Hong_Kong")

def now_str():
    """返回当前时间的字符串（香港时区）"""
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")

# ============================================================
# 数据库
# ============================================================
_here = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_here, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "registrations.db")


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
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            project TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON registrations(project)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_employee ON registrations(employee_id)")
    conn.commit()
    conn.close()


def login_or_register(employee_id, name):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        cur = conn.execute("SELECT name FROM employees WHERE employee_id = ?", (employee_id,))
        row = cur.fetchone()
        if row:
            return row[0], False
        conn.execute(
            "INSERT INTO employees (employee_id, name, created_at) VALUES (?, ?, ?)",
            (employee_id, name, now_str()),          # ← 使用 now_str()
        )
        conn.commit()
        return name, True
    finally:
        conn.close()


def get_counts():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute("SELECT project, COUNT(*) FROM registrations GROUP BY project")
    data = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return data


def register(employee_id, project):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")

        cur = conn.execute("SELECT COUNT(*) FROM registrations WHERE project = ?", (project,))
        count = cur.fetchone()[0]
        if count >= MAX_PER_PROJECT:
            conn.execute("ROLLBACK")
            return False, count, 0, "project_full"

        cur = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE project = ? AND employee_id = ?",
            (project, employee_id),
        )
        if cur.fetchone()[0] > 0:
            conn.execute("ROLLBACK")
            return False, count, 0, "duplicate"

        cur = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE employee_id = ?", (employee_id,)
        )
        person_count = cur.fetchone()[0]
        if person_count >= MAX_PER_PERSON:
            conn.execute("ROLLBACK")
            return False, count, person_count, "person_limit"

        conn.execute(
            "INSERT INTO registrations (employee_id, project, created_at) VALUES (?, ?, ?)",
            (employee_id, project, now_str()),       # ← 使用 now_str()
        )
        conn.execute("COMMIT")
        return True, count + 1, person_count + 1, "ok"
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def get_my_registrations(employee_id):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute(
        "SELECT id, project, created_at FROM registrations WHERE employee_id = ? ORDER BY created_at",
        (employee_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def cancel_registration(reg_id, employee_id):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "SELECT project FROM registrations WHERE id = ? AND employee_id = ?",
            (reg_id, employee_id),
        )
        row = cur.fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return False, None
        conn.execute("DELETE FROM registrations WHERE id = ?", (reg_id,))
        conn.execute("COMMIT")
        return True, row[0]
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def get_all_registrations():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    df = pd.read_sql_query(
        """SELECT e.employee_id AS 工号, e.name AS 姓名,
                  r.project AS 项目, r.created_at AS 报名时间
           FROM registrations r
           JOIN employees e ON r.employee_id = e.employee_id
           ORDER BY r.project, r.created_at""",
        conn,
    )
    conn.close()
    return df


init_db()

# ============================================================
# session_state
# ============================================================
if "employee_id" not in st.session_state:
    st.session_state.employee_id = None
if "employee_name" not in st.session_state:
    st.session_state.employee_name = None
if "page" not in st.session_state:
    st.session_state.page = "报名"
if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False


# ============================================================
# 登录页面
# ============================================================
def render_login_page():
    st.subheader("🔑 登录 / 首次进入")
    st.caption("请输入您的工号和姓名。工号作为唯一识别码，姓名仅用于显示。")

    with st.form("login_form"):
        employee_id = st.text_input("工号", max_chars=30, placeholder="请输入您的工号")
        name = st.text_input("姓名", max_chars=30, placeholder="请输入您的姓名")
        submitted = st.form_submit_button("进入报名系统", type="primary", use_container_width=True)

    if submitted:
        employee_id = employee_id.strip()
        name = name.strip()
        if not employee_id:
            st.warning("⚠️ 请填写工号")
        elif not name:
            st.warning("⚠️ 请填写姓名")
        else:
            stored_name, is_new = login_or_register(employee_id, name)
            st.session_state.employee_id = employee_id
            st.session_state.employee_name = stored_name
            if is_new:
                st.success(f"✅ 欢迎首次使用，{stored_name}（工号：{employee_id}）")
            else:
                st.success(f"✅ 欢迎回来，{stored_name}（工号：{employee_id}）")
            st.rerun()

    st.divider()
    if st.button("🔐 管理员入口", use_container_width=False):
        st.session_state.page = "管理员"
        st.rerun()


# ============================================================
# 报名页面
# ============================================================
def render_registration_page():
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(
            f"👤 当前用户：**{st.session_state.employee_name}**"
            f"（工号：`{st.session_state.employee_id}`）"
        )
    with c2:
        if st.button("退出登录", use_container_width=True):
            st.session_state.employee_id = None
            st.session_state.employee_name = None
            st.rerun()

    st.divider()

    if "reg_result" in st.session_state:
        r = st.session_state.pop("reg_result")
        if r["ok"]:
            st.success(
                f"✅ 报名成功！**{r['project']}**"
                f"（该项目 {r['count']}/{MAX_PER_PROJECT}，您已报 {r['person_count']}/{MAX_PER_PERSON} 个）"
            )
            st.balloons()
        else:
            if r["status"] == "project_full":
                st.error(f"❌ **{r['project']}** 已满（{r['count']}/{MAX_PER_PROJECT}），请选择其他项目。")
            elif r["status"] == "person_limit":
                st.error(
                    f"❌ 您已报名 **{r['person_count']}/{MAX_PER_PERSON}** 个项目，已达上限。"
                    "如需报名新项目，请先在下方「我的报名」中取消一个。"
                )
            elif r["status"] == "duplicate":
                st.warning(f"⚠️ 您已报名过 **{r['project']}**，无需重复报名。")

    st.subheader("📊 各项目报名情况")
    counts = get_counts()
    for cat_name, cat_projects in PROJECT_CATEGORIES.items():
        st.markdown(f"#### {cat_name}")
        cols = st.columns(3)
        for i, proj in enumerate(cat_projects):
            cnt = counts.get(proj, 0)
            with cols[i % 3]:
                if cnt >= MAX_PER_PROJECT:
                    st.error(f"**{proj}**\n\n🔴 已满  {cnt}/{MAX_PER_PROJECT}")
                else:
                    st.success(f"**{proj}**\n\n🟢 已报名  {cnt}/{MAX_PER_PROJECT}")

    st.divider()

    st.subheader("✍️ 提交报名")
    with st.form("register_form", clear_on_submit=True):
        project = st.selectbox("选择参赛项目", PROJECTS)
        submitted = st.form_submit_button("提交报名", type="primary", use_container_width=True)

    if submitted:
        try:
            ok, count, person_count, status = register(st.session_state.employee_id, project)
            st.session_state["reg_result"] = {
                "ok": ok,
                "project": project,
                "count": count,
                "person_count": person_count,
                "status": status,
            }
            st.rerun()
        except Exception as e:
            st.error(f"系统错误：{e}")

    st.divider()

    st.subheader("📋 我的报名")
    rows = get_my_registrations(st.session_state.employee_id)
    if not rows:
        st.info(f"您尚未报名任何项目。每人最多可报 **{MAX_PER_PERSON}** 个项目。")
    else:
        st.caption(
            f"您已报名 **{len(rows)}/{MAX_PER_PERSON}** 个项目，"
            f"还可报 **{MAX_PER_PERSON - len(rows)}** 个。"
        )
        for reg_id, proj, ts in rows:
            c1, c2 = st.columns([5, 1])
            with c1:
                st.markdown(f"**{proj}**")
                st.caption(f"报名时间：{ts}")
            with c2:
                if st.button("取消报名", key=f"cancel_{reg_id}", use_container_width=True):
                    ok, cancelled_project = cancel_registration(
                        reg_id, st.session_state.employee_id
                    )
                    if ok:
                        st.success(f"✅ 已取消 **{cancelled_project}** 的报名。")
                        st.rerun()
                    else:
                        st.error("取消失败，请重试。")
            st.divider()


# ============================================================
# 管理员页面
# ============================================================
def render_admin_page():
    st.subheader("🔐 管理员页面")

    if st.button("← 返回报名页面"):
        st.session_state.page = "报名"
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

    # 刷新按钮 + 标题
    c1, c2 = st.columns([4, 1])
    with c1:
        st.subheader("📋 全部报名名单")
    with c2:
        if st.button("🔄 刷新数据", use_container_width=True, type="primary"):
            st.rerun()

    # 显示最后刷新时间
    st.caption(f"最后刷新时间：{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}")

    df = get_all_registrations()

    if df.empty:
        st.info("暂无报名记录。")
        return

    st.caption(
        f"共 **{len(df)}** 条报名记录，"
        f"**{df['工号'].nunique()}** 位参赛者"
    )

    person_summary = df.groupby(["工号", "姓名"], as_index=False).agg(
        报名数量=("项目", "count"),
        报名项目=("项目", lambda x: " ｜ ".join(x)),
    ).sort_values("报名数量", ascending=False)

    tab1, tab2 = st.tabs(["📋 明细列表", "👥 按人汇总"])
    with tab1:
        st.dataframe(df, use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(person_summary, use_container_width=True, hide_index=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="报名明细")
        person_summary.to_excel(writer, index=False, sheet_name="按人汇总")
    output.seek(0)
    timestamp = datetime.now(TZ).strftime("%Y%m%d_%H%M%S")   # ← 使用 TZ
    st.download_button(
        label="📥 下载报名名单 (Excel，含明细和按人汇总)",
        data=output,
        file_name=f"报名名单_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.divider()

    st.subheader("📊 按项目统计")
    stat = df.groupby("项目").size().reset_index(name="报名人数")
    stat["状态"] = stat["报名人数"].apply(
        lambda x: "🔴 已满" if x >= MAX_PER_PROJECT else "🟢 可报名"
    )
    stat = stat.sort_values("项目")
    st.dataframe(stat, use_container_width=True, hide_index=True)


# ============================================================
# 渲染路由
# ============================================================
if st.session_state.page == "管理员":
    render_admin_page()
else:
    if st.session_state.employee_id is None:
        render_login_page()
    else:
        render_registration_page()

st.divider()
st.caption(
    f"📌 说明：每个项目限 {MAX_PER_PROJECT} 人，每人最多报 {MAX_PER_PERSON} 个项目，"
    "按提交时间先后顺序，满员后无法再报名。"
)
