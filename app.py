"""
中国上市公司个人投资分析工具
基于 Streamlit + SQLite
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import urllib.request
import json
import ssl
import urllib.parse

# ── 页面配置 ──
st.set_page_config(
    page_title="A股投资分析工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 自定义CSS ──
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stCard { border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; }
    div[data-testid="stSidebar"] { background-color: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #eee !important; }
    .card-title { font-size: 1.1rem; font-weight: 600; color: #1a1a2e; }
    .card-meta { font-size: 0.8rem; color: #888; }
</style>
""", unsafe_allow_html=True)

# ── 数据库初始化 ──
DB_PATH = os.path.join(os.path.dirname(__file__), "stock_analysis.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            fundamental TEXT DEFAULT '',
            risk TEXT DEFAULT '',
            plan TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    """)
    # 预设分类
    defaults = ["核心资产", "高股息", "科技成长", "周期股", "观察仓"]
    for d in defaults:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (d,))
    conn.commit()
    conn.close()

init_db()

# ── 预设分类 ──
DEFAULT_CATEGORIES = ["核心资产", "高股息", "科技成长", "周期股", "观察仓"]

def get_categories():
    conn = get_db()
    rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]

def get_all_companies():
    conn = get_db()
    rows = conn.execute("SELECT * FROM companies ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_company(code):
    conn = get_db()
    row = conn.execute("SELECT * FROM companies WHERE code = ?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None

def save_company(code, name, category, fundamental, risk, plan):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = get_db()
    existing = conn.execute("SELECT code FROM companies WHERE code = ?", (code,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE companies SET name=?, category=?, fundamental=?, risk=?, plan=?, updated_at=?
            WHERE code=?
        """, (name, category, fundamental, risk, plan, now, code))
    else:
        conn.execute("""
            INSERT INTO companies (code, name, category, fundamental, risk, plan, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (code, name, category, fundamental, risk, plan, now, now))
    conn.commit()
    conn.close()

def delete_company(code):
    conn = get_db()
    conn.execute("DELETE FROM companies WHERE code = ?", (code,))
    conn.commit()
    conn.close()

def add_category(name):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

# ── 侧边栏导航 ──
st.sidebar.title("📊 A股投资分析")
st.sidebar.markdown("---")
menu = st.sidebar.radio(
    "导航菜单",
    ["📝 新增公司", "📂 我的股票池", "📋 全部记录", "📤 导出数据"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")
st.sidebar.caption(f"💡 数据库: {DB_PATH}")

# ══════════════════════════════════════
# 📝 新增/编辑公司
# ══════════════════════════════════════
if menu == "📝 新增公司":
    # 检查URL参数判断是否编辑模式
    params = st.query_params
    edit_code = params.get("edit", None)

    # ── 自动查询股票名称 ──
    def search_stock(keyword):
        """通过东方财富API搜索股票代码/名称"""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={urllib.parse.quote(keyword)}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            results = data.get("QuotationCodeTable", {}).get("Data", [])
            # 只保留A股
            return [(r["Code"], r["Name"], r.get("SecurityTypeName", "")) for r in results if r.get("Classify") == "AStock"]
        except:
            return []

        if edit_code:
        st.subheader(f"✏️ 编辑公司: {edit_code}")
        comp = get_company(edit_code)
        if comp:
            default_name = comp["name"]
            default_cat = comp["category"]
            default_fund = comp["fundamental"]
            default_risk = comp["risk"]
            default_plan = comp["plan"]
        else:
            st.error("未找到该公司"); st.stop()
    else:
        st.subheader("📝 新增公司分析")
        default_name = ""; default_cat = DEFAULT_CATEGORIES[0]
        default_fund = ""; default_risk = ""; default_plan = ""

    col1, col2, col3 = st.columns([2, 3, 1])
    with col1:
        code = st.text_input("股票代码", value=edit_code or "", 
                             disabled=edit_code is not None,
                             placeholder="如 600519")
    with col2:
        name = st.text_input("公司名称", value=default_name, placeholder="如 贵州茅台")
    with col3:
        st.write("")  # spacer
        search_btn = st.button("🔍 查询")

    # 自动搜索逻辑
    if search_btn and code:
        results = search_stock(code.strip())
        if results:
            st.session_state["search_results"] = results
        else:
            st.warning("未找到匹配的A股，请手动输入")

    # 显示搜索结果供选择
    if "search_results" in st.session_state and st.session_state["search_results"] and not edit_code:
        results = st.session_state["search_results"]
        options = [f"{r[0]} - {r[1]} ({r[2]})" for r in results]
        selected = st.selectbox("📋 选择股票", options, index=0)
        if selected:
            idx = options.index(selected)
            # 自动填充（只在用户没手动改过时）
            if not edit_code:
                st.session_state["auto_code"] = results[idx][0]
                st.session_state["auto_name"] = results[idx][1]
                code = results[idx][0]
                name = results[idx][1]
        st.caption("💡 已自动填充代码和名称")

    categories = get_categories()
    cat_col1, cat_col2 = st.columns([3, 2])
    with cat_col1:
        selected_cat = st.selectbox("分类", categories,
                                    index=categories.index(default_cat) if default_cat in categories else 0)
    with cat_col2:
        new_cat = st.text_input("或输入新分类", placeholder="自定义分类名")
    
    category = new_cat.strip() if new_cat.strip() else selected_cat

    st.markdown("---")
    fundamental = st.text_area("📈 基本面分析", value=default_fund, height=150,
                               placeholder="财务亮点、护城河、竞争优势...")
    risk = st.text_area("⚠️ 风险提示", value=default_risk, height=120,
                        placeholder="潜在雷区、行业风险、政策风险...")
    plan = st.text_area("🎯 操作计划", value=default_plan, height=120,
                        placeholder="买入/卖出逻辑、目标价位、仓位规划...")

    if st.button("💾 保存分析", type="primary", use_container_width=True):
        if not code or not name:
            st.error("请填写股票代码和公司名称")
        else:
            if new_cat.strip():
                add_category(new_cat.strip())
            save_company(code.strip(), name.strip(), category, fundamental, risk, plan)
            st.success(f"✅ {name}({code}) 分析已保存！")
            if edit_code:
                st.query_params.clear()
                st.rerun()

# ══════════════════════════════════════
# 📂 我的股票池
# ══════════════════════════════════════
elif menu == "📂 我的股票池":
    st.subheader("📂 我的股票池")
    categories = get_categories()
    companies = get_all_companies()

    if not companies:
        st.info("还没有添加任何公司，去「新增公司」开始吧！")
    else:
        selected = st.selectbox("选择分类查看", ["全部"] + categories)
        
        filtered = companies if selected == "全部" else [c for c in companies if c["category"] == selected]
        
        if not filtered:
            st.warning(f"「{selected}」分类下暂无公司")
        else:
            st.caption(f"共 {len(filtered)} 家公司")
            for comp in filtered:
                with st.container():
                    col_title, col_btn = st.columns([4, 1])
                    with col_title:
                        st.markdown(f"**{comp['name']}** ({comp['code']})  ·  `{comp['category']}`")
                        st.caption(f"更新于 {comp['updated_at']}")
                    with col_btn:
                        if st.button("🗑️", key=f"del_{comp['code']}", help="删除"):
                            delete_company(comp["code"])
                            st.rerun()

                    with st.expander("📄 查看分析详情"):
                        if comp["fundamental"]:
                            st.markdown("**📈 基本面分析**")
                            st.write(comp["fundamental"])
                        if comp["risk"]:
                            st.markdown("**⚠️ 风险提示**")
                            st.write(comp["risk"])
                        if comp["plan"]:
                            st.markdown("**🎯 操作计划**")
                            st.write(comp["plan"])
                        
                        if st.button("✏️ 编辑", key=f"edit_{comp['code']}"):
                            st.query_params["edit"] = comp["code"]
                            st.rerun()
                    st.markdown("---")

# ══════════════════════════════════════
# 📋 全部记录
# ══════════════════════════════════════
elif menu == "📋 全部记录":
    st.subheader("📋 全部分析记录")
    companies = get_all_companies()
    if not companies:
        st.info("暂无记录")
    else:
        df = pd.DataFrame(companies)
        df = df[["code", "name", "category", "updated_at"]]
        df.columns = ["代码", "名称", "分类", "更新时间"]
        st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════
# 📤 导出
# ══════════════════════════════════════
elif menu == "📤 导出数据":
    st.subheader("📤 导出数据")
    companies = get_all_companies()
    if not companies:
        st.info("暂无数据可导出")
    else:
        df = pd.DataFrame(companies)
        
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button("📥 导出 CSV", csv, "stock_analysis.csv", "text/csv",
                              use_container_width=True)
        with col2:
            st.info("Excel导出已禁用，请用CSV")
        
        st.caption(f"共 {len(df)} 条记录")
