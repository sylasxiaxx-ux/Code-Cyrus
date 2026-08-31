import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import openpyxl
import os
from datetime import datetime

# ---------- 页面标题 ----------
st.set_page_config(page_title="品类偏好报告 - 品牌/单品汇总", layout="wide")
st.title("📊 品类偏好报告 - 品牌 & 单品汇总")

# ---------- 初始化 session_state ----------
if "id_nickname_df" not in st.session_state:
    st.session_state.id_nickname_df = None
if "temp_nickname_edit" not in st.session_state:
    st.session_state.temp_nickname_edit = None
if "computed_tables" not in st.session_state:
    st.session_state.computed_tables = None
if "unmatched_df" not in st.session_state:
    st.session_state.unmatched_df = None
if "raw_dfs" not in st.session_state:
    st.session_state.raw_dfs = None
if "mapping_source" not in st.session_state:
    st.session_state.mapping_source = None

# ---------- 加载默认映射表 ----------
def load_default_mapping():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_path = os.path.join(base_dir, "data", "竞品id匹配_0723updated.xlsx")
    if os.path.exists(default_path):
        try:
            df = pd.read_excel(default_path)
            required_cols = ['id', '类目', 'nickname']
            if all(col in df.columns for col in required_cols):
                df = df[required_cols].copy()
                df['id'] = df['id'].astype(str)
                st.session_state.id_nickname_df = df
                st.session_state.mapping_source = 'default'
                return True
            else:
                st.warning(f"默认映射表列名不正确，需要: {', '.join(required_cols)}")
                return False
        except Exception as e:
            st.warning(f"读取默认映射表失败: {e}")
            return False
    else:
        st.info("未找到默认映射表 data/竞品id匹配_0723updated.xlsx，请上传映射表。")
        return False

# ---------- 核心解析函数 ----------
def parse_preference_json(json_str):
    """
    解析品类偏好 JSON，返回 DataFrame
    要求 JSON 包含 'datas' 数组，其中必须有 'brand_name', 'item_name', 'item_id' 以及数值字段（如 sum_byr_cnt）
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        st.error("JSON 格式错误，请检查语法。")
        return None

    datas = data.get('datas')
    if datas is None:
        st.error("JSON 中缺少 'datas' 字段，请检查格式。")
        return None

    # 构建字段字典
    field_dict = {}
    for item in datas:
        name = item.get('name')
        values = item.get('values')
        if name and values is not None:
            field_dict[name] = values

    # 必须字段
    required = ['brand_name', 'item_name', 'item_id']
    missing = [f for f in required if f not in field_dict]
    if missing:
        st.error(f"JSON 中缺少必要字段: {missing}，请检查格式。")
        return None

    # 数值字段候选
    value_candidates = ['sum_byr_cnt', 'purchase_byr_tb_ratio', 'preference_value', 'value']
    value_field = None
    for cand in value_candidates:
        if cand in field_dict:
            value_field = cand
            break
    if value_field is None:
        st.error(f"未找到数值字段（尝试了: {', '.join(value_candidates)}），请检查 JSON 字段名。")
        return None

    # 构建 DataFrame
    df = pd.DataFrame({
        '品牌名': field_dict['brand_name'],
        '单品': field_dict['item_name'],
        'ID': field_dict['item_id'],
        '偏好值': field_dict[value_field]
    })
    df['偏好值'] = pd.to_numeric(df['偏好值'], errors='coerce')
    # 过滤掉单品名为 '-' 的行
    df = df[df['单品'] != '-']
    # 去重
    df = df.drop_duplicates(subset=['ID', '单品', '品牌名'], keep='first')
    df.index = pd.RangeIndex(start=1, stop=len(df)+1)
    return df, value_field

# ---------- 匹配 nickname ----------
def match_nickname(df, id_nickname_df):
    df = df.copy()
    df['ID'] = df['ID'].astype(str)
    id_nickname_df = id_nickname_df.copy()
    id_nickname_df['id'] = id_nickname_df['id'].astype(str)
    nickname_map = id_nickname_df[['id', 'nickname']].rename(columns={'id':'ID'})
    merged = df.merge(nickname_map, on='ID', how='left')
    unmatched = merged[merged['nickname'].isna() | (merged['nickname'] == '-')][['ID', '单品', '品牌名']]
    unmatched = unmatched.drop_duplicates(subset=['ID'])
    unmatched.index = pd.RangeIndex(start=1, stop=len(unmatched)+1)
    return merged, unmatched

# ---------- 按 nickname 汇总 ----------
def aggregate_by_nickname(merged_df):
    clean = merged_df[~merged_df['nickname'].isna() & (merged_df['nickname'] != '-')]
    if clean.empty:
        return pd.DataFrame(columns=['nickname', '总偏好值'])
    agg = clean.groupby('nickname', as_index=False)['偏好值'].sum().rename(columns={'偏好值':'总偏好值'})
    agg = agg.sort_values('总偏好值', ascending=False)
    agg.index = pd.RangeIndex(start=1, stop=len(agg)+1)
    return agg

# ---------- 品牌汇总 ----------
def brand_aggregate(df, value_label):
    brand_agg = df.groupby('品牌名', as_index=False)['偏好值'].sum().rename(columns={'偏好值':'总' + value_label})
    brand_agg = brand_agg.sort_values('总' + value_label, ascending=False)
    brand_agg.index = pd.RangeIndex(start=1, stop=len(brand_agg)+1)
    return brand_agg

# ---------- 主界面 ----------
with st.expander("📥 输入数据", expanded=True):
    total_qty = st.number_input("总人数（可选，用于计算占比）", min_value=0, value=1, step=1000, help="输入总人数后，每个单品的偏好值将除以总人数得到占比。若不需缩放，保持默认1。")

    # 一个 JSON 输入框（包含品牌和单品）
    json_input = st.text_area(
        "📄 粘贴品类偏好 JSON 代码",
        height=200,
        placeholder='粘贴包含 "brand_name", "item_name", "item_id" 及数值字段（如 sum_byr_cnt）的 JSON 数据...',
        key="json_input_single"
    )

    st.markdown("**📎 上传 id-nickname 映射表 (Excel)**")
    st.caption("若不上传，将尝试从 data/竞品id匹配_0723updated.xlsx 读取默认映射表。")
    uploaded_mapping = st.file_uploader("必须包含 'id', '类目', 'nickname' 三列", type=["xlsx"], key="mapping_upload_single")

    if uploaded_mapping is not None:
        try:
            new_mapping = pd.read_excel(uploaded_mapping)
            required_cols = ['id', '类目', 'nickname']
            if not all(col in new_mapping.columns for col in required_cols):
                st.error(f"映射表必须包含列: {', '.join(required_cols)}")
            else:
                new_mapping = new_mapping[required_cols].copy()
                new_mapping['id'] = new_mapping['id'].astype(str)
                st.session_state.id_nickname_df = new_mapping
                st.session_state.mapping_source = 'uploaded'
                st.success(f"映射表上传成功，共 {len(new_mapping)} 条记录。")
        except Exception as e:
            st.error(f"读取映射表失败: {e}")
    else:
        if st.session_state.id_nickname_df is None:
            if load_default_mapping():
                st.success(f"已加载默认映射表 (data/竞品id匹配_0723updated.xlsx)，共 {len(st.session_state.id_nickname_df)} 条记录。")

    if st.session_state.id_nickname_df is not None:
        source = "上传" if st.session_state.mapping_source == 'uploaded' else "默认(data/竞品id匹配_0723updated.xlsx)"
        st.info(f"✅ 当前映射表来源: {source}，共 {len(st.session_state.id_nickname_df)} 条记录。")

    run_btn = st.button("🚀 运行分析", type="primary")

# ---------- 执行分析 ----------
if run_btn:
    if not json_input.strip():
        st.error("请粘贴品类偏好 JSON 代码！")
    elif st.session_state.id_nickname_df is None:
        st.error("请上传映射表或确保 data/竞品id匹配_0723updated.xlsx 存在。")
    else:
        try:
            df_raw, value_field = parse_preference_json(json_input)
            if df_raw is None:
                st.stop()

            # 应用人数缩放
            if total_qty > 1:
                df_raw['偏好值'] = df_raw['偏好值'] / total_qty
                value_label = "占比"
            else:
                value_label = "偏好值"

            # 匹配 nickname
            merged_df, unmatched = match_nickname(df_raw, st.session_state.id_nickname_df)
            # 按 nickname 汇总
            agg_df = aggregate_by_nickname(merged_df)
            # 品牌汇总
            brand_agg = brand_aggregate(df_raw, value_label)

            # 保存结果
            st.session_state.raw_dfs = {
                'df_raw': df_raw,
                'merged_df': merged_df,
                'agg_df': agg_df,
                'brand_agg': brand_agg,
                'value_label': value_label
            }
            st.session_state.unmatched_df = unmatched
            st.session_state.computed_tables = {
                'df_raw': df_raw,
                'merged_df': merged_df,
                'agg_df': agg_df,
                'brand_agg': brand_agg,
                'unmatched': unmatched,
                'value_label': value_label
            }
            st.success(f"分析完成！共解析 {len(df_raw)} 条单品记录。")

        except json.JSONDecodeError as e:
            st.error(f"JSON 格式错误: {e}")
        except Exception as e:
            st.error(f"处理出错: {e}")
            st.exception(e)

# ---------- 显示结果 ----------
if st.session_state.computed_tables is not None:
    tables = st.session_state.computed_tables
    unmatched = tables['unmatched']
    merged_df = tables['merged_df']
    agg_df = tables['agg_df']
    brand_agg = tables['brand_agg']
    value_label = tables.get('value_label', '偏好值')

    # 未匹配编辑区域
    if len(unmatched) > 0:
        st.subheader("⚠️ 发现未匹配的ID，请补充类目和nickname")
        st.info(f"共有 {len(unmatched)} 个ID未匹配到nickname。请在下方表格中为每个ID填写对应的「类目」和「nickname」，然后点击“更新映射并重新计算”。")

        with st.expander("📋 查看当前映射表中已有的 nickname（可按类目筛选 / 关键词搜索）", expanded=True):
            if st.session_state.id_nickname_df is not None:
                ref_df = st.session_state.id_nickname_df[['类目', 'nickname']].drop_duplicates().sort_values(['类目', 'nickname'])
                keyword = st.text_input("🔍 输入品牌名（或关键词）搜索 nickname", placeholder="例如：雅诗兰黛")
                all_categories = sorted(ref_df['类目'].unique())
                selected_categories = st.multiselect(
                    "选择类目（空选则显示全部）",
                    options=all_categories,
                    default=[],
                    key="category_filter_single"
                )
                if selected_categories:
                    filtered_df = ref_df[ref_df['类目'].isin(selected_categories)]
                else:
                    filtered_df = ref_df
                if keyword:
                    filtered_df = filtered_df[filtered_df['nickname'].str.contains(keyword, case=False, na=False)]
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
                st.caption("💡 提示：可同时使用类目筛选和关键词搜索，结果取交集。")
            else:
                st.info("当前无映射表数据。")

        edit_df = unmatched[['ID', '单品', '品牌名']].copy()
        edit_df['类目'] = ""
        edit_df['nickname'] = ""

        if st.session_state.temp_nickname_edit is not None:
            temp = st.session_state.temp_nickname_edit
            edit_df = edit_df.merge(temp[['ID', '类目', 'nickname']], on='ID', how='left', suffixes=('', '_new'))
            edit_df['类目'] = edit_df['类目_new'].fillna(edit_df['类目'])
            edit_df['nickname'] = edit_df['nickname_new'].fillna(edit_df['nickname'])
            edit_df.drop(columns=['类目_new', 'nickname_new'], inplace=True)

        edited = st.data_editor(
            edit_df,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "单品": st.column_config.TextColumn("单品", disabled=True),
                "品牌名": st.column_config.TextColumn("品牌名", disabled=True),
                "类目": st.column_config.TextColumn("类目 (必填)", required=True),
                "nickname": st.column_config.TextColumn("nickname (必填)", required=True),
            },
            hide_index=True,
            use_container_width=True,
            key="edit_unmatched_single"
        )

        if st.button("🔄 更新映射并重新计算"):
            if edited['类目'].isna().any() or (edited['类目'] == '').any() or edited['nickname'].isna().any() or (edited['nickname'] == '').any():
                st.warning("请为所有ID填写完整的「类目」和「nickname」后再更新！")
            else:
                new_mappings = edited[['ID', '类目', 'nickname']].copy()
                new_mappings['ID'] = new_mappings['ID'].astype(str)
                current = st.session_state.id_nickname_df.copy()
                current['id'] = current['id'].astype(str)
                current = current[~current['id'].isin(new_mappings['ID'])]
                updated = pd.concat([current, new_mappings.rename(columns={'ID':'id'})], ignore_index=True)
                updated = updated.sort_values(by=['类目', 'nickname']).reset_index(drop=True)
                st.session_state.id_nickname_df = updated
                st.session_state.temp_nickname_edit = new_mappings
                st.session_state.mapping_source = 'uploaded'

                if st.session_state.raw_dfs is not None:
                    df_raw = st.session_state.raw_dfs['df_raw']
                    merged_new, unmatched_new = match_nickname(df_raw, updated)
                    agg_new = aggregate_by_nickname(merged_new)
                    brand_new = brand_aggregate(df_raw, value_label)
                    st.session_state.computed_tables = {
                        'df_raw': df_raw,
                        'merged_df': merged_new,
                        'agg_df': agg_new,
                        'brand_agg': brand_new,
                        'unmatched': unmatched_new,
                        'value_label': value_label
                    }
                    st.session_state.unmatched_df = unmatched_new
                    st.success(f"✅ 映射已更新！当前映射表共 {len(updated)} 条记录（新增 {len(new_mappings)} 条）。")
                    st.rerun()
                else:
                    st.error("原始数据丢失，请重新运行分析。")

    # 显示结果
    st.subheader(f"📊 品牌汇总（按总{value_label}降序）")
    st.dataframe(brand_agg)

    st.subheader("🛍️ 单品明细（含 nickname）")
    st.dataframe(merged_df[['品牌名', '单品', 'nickname', value_label, 'ID']])

    st.subheader(f"📈 按 nickname 汇总（总{value_label}）")
    st.dataframe(agg_df)

    if len(unmatched) == 0:
        st.success("✅ 所有单品均已匹配到nickname！")

    # 下载映射表
    if st.session_state.id_nickname_df is not None:
        st.markdown("---")
        st.subheader("📥 下载最新映射表")
        st.info("点击下方按钮可下载当前使用的完整映射表（包含所有已补充的 nickname），以便下次直接上传。")
        st.caption(f"📌 当前映射表共 {len(st.session_state.id_nickname_df)} 条记录。")
        export_df = st.session_state.id_nickname_df.copy()
        if 'id' not in export_df.columns:
            export_df = export_df.rename(columns={'ID':'id'})
        export_df = export_df[['id', '类目', 'nickname']]
        export_df = export_df.sort_values(by=['类目', 'nickname']).reset_index(drop=True)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='映射表')
        output.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="📥 下载映射表 (Excel)",
            data=output,
            file_name=f"竞品id匹配_updated_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
