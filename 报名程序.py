import streamlit as st
import sqlite3
import os
from datetime import datetime
import pandas as pd
from io import BytesIO

# ============================================================
# 🔒 隐藏侧边栏导航（不显示 pages/ 下的程序）
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
# ============================================================

st.title("🏆 参赛项目报名")

# ============================================================
# 🔧 配置区
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

MAX_PER_PROJECT = 5      # 每个项目最多 5 人
MAX_PER_PERSON = 3       # 每人最多报 3 个项目

try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except Exception:
    ADMIN_PASSWORD = "admin123"   # ⚠️ 请在 Streamlit Secrets 中配置密码
# ============================================================

# ---------- 数据库路径 ----------
_here = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(_here, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "registrations.db")


# ---------- 数据库操作 ----------
def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON registrations(project)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON registrations(name)")
    conn.commit()
    conn.close()


def get_counts():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute("SELECT project, COUNT(*) FROM registrations GROUP BY project")
    data = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return data


def register(project, name):
    """
    原子化报名，检查：
      1. 项目是否满员
      2. 该姓名是否已报满 3 个项目
      3. 是否已报过此项目
    返回 (是否成功, 当前项目人数, 该姓名已报数量, 状态码)
    状态码: "ok" / "project_full" / "person_limit" / "duplicate"
    """
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")

        # 1. 检查项目满员
        cur = conn.execute("SELECT COUNT(*) FROM registrations WHERE project = ?", (project,))
        count = cur.fetchone()[0]
        if count >= MAX_PER_PROJECT:
            conn.execute("ROLLBACK")
            return False, count, 0, "project_full"

        # 2. 检查是否已报过此项目
        cur = conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE project = ? AND name = ?",
            (project, name),
        )
        if cur.fetchone()[0] > 0:
            conn.execute("ROLLBACK")
            return False, count, 0, "duplicate"

        # 3. 检查该姓名已报数量
        cur = conn.execute("SELECT COUNT(*) FROM registrations WHERE name = ?", (name,))
        person_count = cur.fetchone()[0]
        if person_count >= MAX_PER_PERSON:
            conn.execute("ROLLBACK")
            return False, count, person_count, "person_limit"

        # 4. 插入
        conn.execute(
            "INSERT INTO registrations (project, name, created_at) VALUES (?, ?, ?)",
            (project, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
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


def get_registrations_by_name(name):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cur = conn.execute(
        "SELECT id, project, created_at FROM registrations WHERE name = ? ORDER BY created_at",
        (name,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def cancel_registration(reg_id, name):
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "SELECT project FROM registrations WHERE id = ? AND name = ?", (reg_id, name)
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
        "SELECT name AS 姓名, project AS 项目, created_at AS 报名时间 "
        "FROM registrations ORDER BY project, created_at",
        conn,
    )
    conn.close()
    return df


init_db()


# ============================================================
# ---------- 页面导航 ----------
# ============================================================
if "page" not in st.session_state:
    st.session_state.page = "报名"

c1, c2, c3 = st.columns(3)
with c1:
    if st.button(
        "📝 我要报名",
        use_container_width=True,
        type="primary" if st.session_state.page == "报名" else "secondary",
    ):
        st.session_state.page = "报名"
        st.rerun()
with c2:
    if st.button(
        "❌ 取消报名",
        use_container_width=True,
        type="primary" if st.session_state.page == "取消" else "secondary",
    ):
        st.session_state.page = "取消"
        st.rerun()
with c3:
    if st.button(
        "🔐 管理员",
        use_container_width=True,
        type="primary" if st.session_state.page == "管理员" else "secondary",
    ):
        st.session_state.page = "管理员"
        st.rerun()

st.divider()


# ============================================================
# ---------- 页面 1：报名 ----------
# ============================================================
def render_register_page():
    # 显示上一次报名结果
    if "reg_result" in st.session_state:
        r = st.session_state.pop("reg_result")
        if r["ok"]:
            st.success(
                f"✅ 报名成功！**{r['name']}** 已报名 **{r['project']}**"
                f"（该项目 {r['count']}/{MAX_PER_PROJECT}，"
                f"您已报 {r['person_count']}/{MAX_PER_PERSON} 个项目）"
            )
            st.balloons()
        else:
            if r["status"] == "project_full":
                st.error(
                    f"❌ 报名失败：**{r['project']}** 已满"
                    f"（{r['count']}/{MAX_PER_PROJECT}），请选择其他项目。"
                )
            elif r["status"] == "person_limit":
                st.error(
                    f"❌ 报名失败：您已报名 **{r['person_count']}/{MAX_PER_PERSON}** 个项目，"
                    f"达到上限。如需报名新项目，请先在「取消报名」中撤销一个。"
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

    # ---- 我的报名进度查询 ----
    st.subheader("👤 我的报名进度")
    st.caption(f"每人最多可报 **{MAX_PER_PERSON}** 个项目。")

    check_name = st.text_input(
        "输入姓名查询已报名数量",
        max_chars=30,
        placeholder="请输入您的姓名",
        key="check_name_input",
    )
    if st.button("🔍 查询我的报名进度", key="check_progress_btn"):
        check_name = check_name.strip()
        if not check_name:
            st.warning("⚠️ 请填写姓名")
        else:
            rows = get_registrations_by_name(check_name)
            if not rows:
                st.info(f"**{check_name}** 暂无报名记录，可报名 **{MAX_PER_PERSON}** 个项目。")
            else:
                st.info(
                    f"**{check_name}** 已报名 **{len(rows)}/{MAX_PER_PERSON}** 个项目，"
                    f"还可报 **{MAX_PER_PERSON - len(rows)}** 个。"
                )
                for reg_id, proj, ts in rows:
                    st.markdown(f"- {proj}　<span style='color:gray;font-size:12px;'>（{ts}）</span>",
                                unsafe_allow_html=True)

    st.divider()
    st.subheader("✍️ 提交报名")

    with st.form("register_form", clear_on_submit=True):
        name = st.text_input("参赛人名称", max_chars=30, placeholder="请输入您的姓名")
        project = st.selectbox("选择参赛项目", PROJECTS)
        submitted = st.form_submit_button(
            "提交报名", type="primary", use_container_width=True
        )

    if submitted:
        name = name.strip()
        if not name:
            st.warning("⚠️ 请填写参赛人名称")
        else:
            try:
                ok, count, person_count, status = register(project, name)
                st.session_state["reg_result"] = {
                    "ok": ok,
                    "name": name,
                    "project": project,
                    "count": count,
                    "person_count": person_count,
                    "status": status,
                }
                st.rerun()
            except Exception as e:
                st.error(f"系统错误：{e}")


# ============================================================
# ---------- 页面 2：取消报名 ----------
# ============================================================
def render_cancel_page():
    st.subheader("❌ 取消报名")
    st.caption("请输入报名时使用的姓名，查询并取消您的报名。取消后名额将释放给其他人。")

    cancel_name = st.text_input(
        "参赛人名称", max_chars=30, placeholder="请输入您的姓名", key="cancel_name_input"
    )

    if st.button("🔍 查询我的报名", use_container_width=True):
        cancel_name = cancel_name.strip()
        if not cancel_name:
            st.warning("⚠️ 请填写姓名")
        else:
            st.session_state["cancel_query_name"] = cancel_name

    if "cancel_query_name" in st.session_state:
        qname = st.session_state["cancel_query_name"]
        rows = get_registrations_by_name(qname)
        if not rows:
            st.info(f"未找到 **{qname}** 的报名记录。")
        else:
            st.write(
                f"**{qname}** 的报名记录如下（共 {len(rows)}/{MAX_PER_PERSON} 个），"
                f"点击「取消报名」可撤销："
            )
            for reg_id, proj, ts in rows:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{proj}**")
                    st.caption(f"报名时间：{ts}")
                with c2:
                    if st.button("取消报名", key=f"cancel_{reg_id}", use_container_width=True):
                        ok, cancelled_project = cancel_registration(reg_id, qname)
                        if ok:
                            st.success(f"✅ 已取消 **{qname}** 在 **{cancelled_project}** 的报名。")
                            st.rerun()
                        else:
                            st.error("取消失败，请重试。")
                st.divider()


# ============================================================
# ---------- 页面 3：管理员 ----------
# ============================================================
def render_admin_page():
    st.subheader("🔐 管理员页面")

    if "admin_authed" not in st.session_state:
        st.session_state.admin_authed = False

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

    st.subheader("📋 全部报名名单")
    df = get_all_registrations()

    if df.empty:
        st.info("暂无报名记录。")
        return

    st.caption(f"共 **{len(df)}** 条报名记录，**{df['姓名'].nunique()}** 位参赛者")

    # 按姓名聚合显示每人报名数量
    person_summary = df.groupby("姓名").agg(
        报名数量=("项目", "count"),
        报名项目=("项目", lambda x: " ｜ ".join(x)),
    ).reset_index()
    person_summary = person_summary.sort_values("报名数量", ascending=False)

    tab1, tab2 = st.tabs(["📋 明细列表", "👥 按人汇总"])
    with tab1:
        st.dataframe(df, use_container_width=True, hide_index=True)
    with tab2:
        st.dataframe(person_summary, use_container_width=True, hide_index=True)

    # 导出 Excel（两个 sheet）
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="报名明细")
        person_summary.to_excel(writer, index=False, sheet_name="按人汇总")
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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


# ---------- 渲染当前页面 ----------
if st.session_state.page == "报名":
    render_register_page()
elif st.session_state.page == "取消":
    render_cancel_page()
else:
    render_admin_page()


st.divider()
st.caption(
    f"📌 说明：每个项目限 {MAX_PER_PROJECT} 人，每人最多报 {MAX_PER_PERSON} 个项目，"
    "按提交时间先后顺序，满员后无法再报名。"
)
