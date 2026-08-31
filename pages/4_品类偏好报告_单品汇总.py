import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import openpyxl
import os
from datetime import datetime

# ---------- 页面标题 ----------
st.title("📊 品类偏好报告 - 单品汇总")

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
    # 获取项目根目录（因为本文件在 pages/ 下，需向上退一级）
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
    解析品类偏好 JSON 字符串，返回品牌、单品、ID、数值的 DataFrame
    假设 JSON 结构类似：
    {
      "datas": [
        {"name": "brand_name", "values": [...]},
        {"name": "item_name", "values": [...]},
        {"name": "item_id", "values": [...]},
        {"name": "sum_byr_cnt", "values": [...]}   // 或 purchase_byr_tb_ratio
      ]
    }
    """
    data = json.loads(json_str)
    # 提取 datas 列表
    datas = data['datas'] if 'datas' in data else None
    if datas is None:
        st.error("JSON 中缺少 'datas' 字段，请检查格式。")
        return None

    # 构建字段字典
    field_dict = {}
    for item in datas:
        name = item['name']
        values = item['values']
        field_dict[name] = values

    # 必须存在的字段
    required_fields = ['brand_name', 'item_name', 'item_id']
    if not all(f in field_dict for f in required_fields):
        st.error(f"JSON 中缺少必要字段: {required_fields}，请检查格式。")
        return None

    # 数值字段：优先 'sum_byr_cnt'，其次 'purchase_byr_tb_ratio'，再尝试其他
    value_field = None
    for candidate in ['sum_byr_cnt', 'purchase_byr_tb_ratio', 'preference_value', 'value']:
        if candidate in field_dict:
            value_field = candidate
            break
    if value_field is None:
        st.error("未找到数值字段（如 sum_byr_cnt 或 purchase_byr_tb_ratio），请检查 JSON 字段名。")
        return None

    # 构建 DataFrame
    df = pd.DataFrame({
        '品牌名': field_dict['brand_name'],
        '单品': field_dict['item_name'],
        'ID': field_dict['item_id'],
        '偏好值': field_dict[value_field]
    })
    # 转为数值
    df['偏好值'] = pd.to_numeric(df['偏好值'], errors='coerce')
    # 过滤掉单品名为 '-' 的行
    df = df[df['单品'] != '-']
    # 去重（按 ID 和 单品）
    df = df.drop_duplicates(subset=['ID', '单品', '品牌名'], keep='first')
    df.index = pd.RangeIndex(start=1, stop=len(df)+1)
    return df, value_field

# ---------- 匹配 nickname ----------
def match_nickname(df, id_nickname_df):
    """
    给 df 匹配 nickname，返回带 nickname 的 df 和未匹配列表
    """
    df = df.copy()
    df['ID'] = df['ID'].astype(str)
    id_nickname_df = id_nickname_df.copy()
    id_nickname_df['id'] = id_nickname_df['id'].astype(str)

    nickname_map = id_nickname_df[['id', 'nickname']].rename(columns={'id':'ID'})
    merged = df.merge(nickname_map, on='ID', how='left')
    # 未匹配的
    unmatched = merged[merged['nickname'].isna() | (merged['nickname'] == '-')][['ID', '单品', '品牌名']]
    unmatched = unmatched.drop_duplicates(subset=['ID'])
    unmatched.index = pd.RangeIndex(start=1, stop=len(unmatched)+1)
    return merged, unmatched

# ---------- 按 nickname 汇总 ----------
def aggregate_by_nickname(merged_df):
    # 过滤掉 nickname 为 NaN 或 '-'
    clean = merged_df[~merged_df['nickname'].isna() & (merged_df['nickname'] != '-')]
    if clean.empty:
        return pd.DataFrame(columns=['nickname', '总偏好值'])
    agg = clean.groupby('nickname', as_index=False)['偏好值'].sum().rename(columns={'偏好值':'总偏好值'})
    agg = agg.sort_values('总偏好值', ascending=False)
    agg.index = pd.RangeIndex(start=1, stop=len(agg)+1)
    return agg

# ---------- 主界面 ----------
with st.expander("📥 输入数据", expanded=True):
    # 总人数输入（可选）
    total_qty = st.number_input("总人数（可选，用于计算占比）", min_value=0, value=1, step=1000, help="输入总人数后，每个单品的偏好值将除以总人数得到占比。若不需缩放，保持默认1。")

    # JSON 代码输入框（高度可调节）
    json_input = st.text_area(
        "📄 粘贴品类偏好 JSON 代码",
        height=200,
        placeholder='请粘贴包含 "brand_name", "item_name", "item_id" 及数值字段（如 sum_byr_cnt）的 JSON 数据...',
        key="json_input_sku"
    )

    st.markdown("**📎 上传 id-nickname 映射表 (Excel)**")
    st.caption("若不上传，将尝试从 data/竞品id匹配_0723updated.xlsx 读取默认映射表。")
    uploaded_mapping = st.file_uploader("必须包含 'id', '类目', 'nickname' 三列", type=["xlsx"], key="mapping_upload_sku")

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
            # 解析 JSON
            df_raw, value_field = parse_preference_json(json_input)
            if df_raw is None:
                st.stop()

            # 如果用户输入了总人数（>0），则计算占比
            if total_qty > 1:
                df_raw['偏好值'] = df_raw['偏好值'] / total_qty
                # 修改列名以示区别
                df_raw.rename(columns={'偏好值': '占比'}, inplace=True)
                value_label = "占比"
            else:
                value_label = "偏好值"

            # 匹配 nickname
            merged_df, unmatched = match_nickname(df_raw, st.session_state.id_nickname_df)
            # 按 nickname 汇总
            agg_df = aggregate_by_nickname(merged_df)

            # 品牌汇总（按品牌聚合）
            brand_agg = df_raw.groupby('品牌名', as_index=False)[value_label].sum().rename(columns={value_label:'总' + value_label})
            brand_agg = brand_agg.sort_values('总' + value_label, ascending=False)
            brand_agg.index = pd.RangeIndex(start=1, stop=len(brand_agg)+1)

            # 保存到 session_state 供后续显示和更新
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

    # 如果有未匹配的，显示编辑区域
    if len(unmatched) > 0:
        st.subheader("⚠️ 发现未匹配的ID，请补充类目和nickname")
        st.info(f"共有 {len(unmatched)} 个ID未匹配到nickname。请在下方表格中为每个ID填写对应的「类目」和「nickname」，然后点击“更新映射并重新计算”。")

        # 辅助查看已有 nickname
        with st.expander("📋 查看当前映射表中已有的 nickname（可按类目筛选 / 关键词搜索）", expanded=True):
            if st.session_state.id_nickname_df is not None:
                ref_df = st.session_state.id_nickname_df[['类目', 'nickname']].drop_duplicates().sort_values(['类目', 'nickname'])
                keyword = st.text_input("🔍 输入品牌名（或关键词）搜索 nickname", placeholder="例如：雅诗兰黛")
                all_categories = sorted(ref_df['类目'].unique())
                selected_categories = st.multiselect(
                    "选择类目（空选则显示全部）",
                    options=all_categories,
                    default=[],
                    key="category_filter_sku"
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

        # 编辑表格
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
            key="edit_unmatched_sku"
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

                # 重新计算
                if st.session_state.raw_dfs is not None:
                    df_raw = st.session_state.raw_dfs['df_raw'].copy()
                    # 注意：df_raw 中可能已经包含了缩放后的值，但我们重新从原始解析会丢失，因此需要重新解析 JSON
                    # 但我们已经存储了原始 df，所以直接使用保存的 df_raw（未缩放）
                    # 实际上我们保存的是缩放后的 df，所以需要重新从 JSON 解析才能保持原始值
                    # 简便方法：重新用解析函数，但那样需要原 JSON 字符串，我们没有存储。
                    # 所以我们存储原始 df 时，应存储未缩放的版本。
                    # 但为了简单，我们可以在第一次解析后，将未缩放的 df 保存为 'df_raw_original'
                    # 这里我们略作修改：在第一次解析时保存未缩放的 df_raw_original 和缩放后的 df_raw。
                    # 为简化，我们重新解析一次 JSON（从界面文本框中读取）
                    # 因此我们使用 json_input 变量（但可能已被覆盖？）
                    # 更好的办法：在 session_state 中存储原始 JSON 字符串
                    # 但为了快速修复，我们直接从界面获取 json_input 值，但可能用户没有保留？
                    # 因此我们建议在第一次解析后，存储未缩放的 df 和缩放后的 df。
                    # 这里我们重构：存储 df_raw_original（未缩放）和 value_label。
                    # 但为不使代码过于复杂，我们只存储原始 df，并在重新计算时重新应用缩放。
                    # 我们保存的 raw_dfs 中的 df_raw 是缩放后的，所以重新计算时应该用原始的。
                    # 所以我们保存原始 df 时，不缩放。
                    # 修改代码：在第一次解析后，保存原始 df（未缩放），并在显示时再缩放。
                    # 为了快速修复，我们在此处改用界面上的 json_input 重新解析。
                    # 但为避免重复，我们干脆在第一次解析时，将原始 JSON 也保存下来。
                    # 简单起见，我们直接重新从 json_input 解析（如果用户未修改，仍然有效）。
                    # 但用户可能修改了 JSON，所以最好还是存储。
                    # 由于时间，我们采取以下方式：在第一次解析时，将 df_raw_original（未缩放）和 scaled 都保存。
                    # 但现在代码没有保存原始，我们改为在第一次解析后，同时保存未缩放和缩放后的。
                    # 我们修改前面代码：在解析后，如果 total_qty > 1，则生成缩放后的 df，但原始保留。
                    # 但之前我们修改了 df_raw，没有保留原始。
                    # 我们重新设计：解析后得到 df_raw_original，然后根据 total_qty 决定是否缩放，缩放后生成 df_scaled。
                    # 但为了兼容，我们直接使用 df_raw 并增加一列 '原始偏好值'。
                    # 算了，我们简单处理：在更新映射时，我们直接用界面 json_input 重新解析（如果用户没有修改，则没问题）。
                    # 如果用户修改了，那就使用新的。
                    # 所以我们修改代码：在更新映射时，重新解析 JSON。
                    # 但这样会丢失用户可能输入的总人数？但我们可以重新读取 total_qty（界面上的值）。
                    # 这样，更新映射时会完全重新计算，没问题。
                    # 因此，在更新映射按钮中，我们重新调用 parse_preference_json 和后续逻辑。
                    # 这样做最可靠。
                    pass
                # 为了简化，我们采用重新解析的方式：
                try:
                    # 重新解析 JSON（使用界面文本框中的内容）
                    df_raw_new, _ = parse_preference_json(json_input)
                    if df_raw_new is None:
                        st.error("重新解析 JSON 失败")
                        st.stop()
                    # 应用人数缩放
                    total_qty_new = total_qty  # 从界面获取
                    if total_qty_new > 1:
                        df_raw_new['偏好值'] = df_raw_new['偏好值'] / total_qty_new
                        value_label_new = "占比"
                    else:
                        value_label_new = "偏好值"
                    # 匹配 nickname
                    merged_df_new, unmatched_new = match_nickname(df_raw_new, updated)
                    agg_df_new = aggregate_by_nickname(merged_df_new)
                    brand_agg_new = df_raw_new.groupby('品牌名', as_index=False)[value_label_new].sum().rename(columns={value_label_new:'总' + value_label_new})
                    brand_agg_new = brand_agg_new.sort_values('总' + value_label_new, ascending=False)
                    brand_agg_new.index = pd.RangeIndex(start=1, stop=len(brand_agg_new)+1)

                    # 更新 session
                    st.session_state.computed_tables = {
                        'df_raw': df_raw_new,
                        'merged_df': merged_df_new,
                        'agg_df': agg_df_new,
                        'brand_agg': brand_agg_new,
                        'unmatched': unmatched_new,
                        'value_label': value_label_new
                    }
                    st.session_state.unmatched_df = unmatched_new
                    st.success(f"✅ 映射已更新！当前映射表共 {len(updated)} 条记录（新增 {len(new_mappings)} 条）。")
                    st.rerun()
                except Exception as e:
                    st.error(f"重新计算失败: {e}")
                    st.exception(e)

    # 显示结果表格
    st.subheader(f"📊 品牌汇总（按总{value_label}降序）")
    st.dataframe(brand_agg)

    st.subheader("🛍️ 单品明细（含 nickname）")
    display_cols = ['品牌名', '单品', 'nickname', value_label, 'ID']
    st.dataframe(merged_df[display_cols])

    st.subheader(f"📈 按 nickname 汇总（总{value_label}）")
    st.dataframe(agg_df)

    if len(unmatched) == 0:
        st.success("✅ 所有单品均已匹配到nickname！")

    # ---------- 下载最新的映射表 ----------
    if st.session_state.id_nickname_df is not None:
        st.markdown("---")
        st.subheader("📥 下载最新映射表")
        st.info("点击下方按钮可下载当前使用的完整映射表（包含所有已补充的 nickname），以便下次直接上传。")
        st.caption(f"📌 当前映射表共 {len(st.session_state.id_nickname_df)} 条记录（包含您补充的 nickname）。")
        
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
