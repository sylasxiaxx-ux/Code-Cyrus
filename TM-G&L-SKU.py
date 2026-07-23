import streamlit as st
import pandas as pd
import numpy as np
import json
from io import BytesIO
import openpyxl
import os

# ---------- 页面配置 ----------
st.set_page_config(page_title="流入流出净值分析-SKU）", layout="wide")
st.title("📊 品牌/单品流入流出净值分析")

# ---------- 初始化 session_state ----------
if "id_nickname_df" not in st.session_state:
    st.session_state.id_nickname_df = None          # 存储当前使用的映射表
if "temp_nickname_edit" not in st.session_state:
    st.session_state.temp_nickname_edit = None      # 编辑中的新映射（暂存）
if "computed_tables" not in st.session_state:
    st.session_state.computed_tables = None         # 缓存计算结果
if "unmatched_df" not in st.session_state:
    st.session_state.unmatched_df = None            # 当前未匹配的ID清单
if "raw_dfs" not in st.session_state:
    st.session_state.raw_dfs = None                 # 存储原始未合并的流入流出df
if "mapping_source" not in st.session_state:
    st.session_state.mapping_source = None          # 映射表来源（'default' 或 'uploaded'）

# ---------- 核心处理函数 ----------
def parse_json_to_dfs(json_str1, json_str2, json_str3, json_str4, out_qty, in_qty):
    """解析四段JSON，返回六个DataFrame：品牌流失、单品流失、品牌流入、单品流入、品牌净值、单品净值（带nickname）"""
    # 品牌流失
    data1 = json.loads(json_str1)
    df1 = pd.DataFrame(data1)
    df_sales = pd.DataFrame(df1.loc['datas','body']) 
    df_sales = pd.DataFrame(df_sales.loc[2,'values'])
    df_sales = df_sales[0]
    df_axises = pd.DataFrame(df1.loc['datas','body'])
    df_axises = pd.DataFrame(df_axises.loc[1,'values'])
    df_axises = df_axises[0]
    df_pct_outflow = []
    for i in df_sales: 
        try: 
            df_pct_outflow.append(float(i) / out_qty) 
        except ValueError: 
            df_pct_outflow.append(None)
    index1 = pd.RangeIndex(start=1, stop=len(df_axises) + 1) 
    df_brand_outflow = pd.DataFrame({
        '品牌名': df_axises,
        '流出人数(指数)': df_sales,
        '人数占比': df_pct_outflow
    })
    df_brand_outflow = df_brand_outflow.sort_values(by='人数占比', ascending=False)
    df_brand_outflow.index = index1

    # 单品流失
    data2 = json.loads(json_str2)
    df2 = pd.DataFrame(data2)
    df_sales2 = pd.DataFrame(df2.loc['datas','body']) 
    df_sale2 = df_sales2.loc[2,'values']
    item_id = df_sales2.loc[0,'values']
    df_axise2 = pd.DataFrame(df2.loc['axises','body'])
    itemname = df_axise2.loc[1,'values']
    itembrand = df_axise2.loc[2,'values']
    df_pct2 = []
    for i in df_sale2: 
        try: 
            df_pct2.append(float(i) / out_qty) 
        except ValueError: 
            df_pct2.append(None)
    df_item_outflow_raw = pd.DataFrame({
        '单品': [item['key'] for item in itemname], 
        '品牌': [brand['key'] for brand in itembrand], 
        '流出人数': df_sale2,
        '人数占比': df_pct2,
        'ID': item_id
    })
    df_item_outflow_raw = df_item_outflow_raw[df_item_outflow_raw['单品'] != '-']
    df_item_outflow_raw = df_item_outflow_raw.drop_duplicates(subset=['ID', '单品', '品牌'], keep='first')
    df_item_outflow_raw.index = pd.RangeIndex(start=1, stop=len(df_item_outflow_raw)+1)

    # 品牌流入
    data3 = json.loads(json_str3)
    df3 = pd.DataFrame(data3)
    df_sales3 = pd.DataFrame(df3.loc['datas','body']) 
    df_sales3 = pd.DataFrame(df_sales3.loc[2,'values'])
    df_sales3 = df_sales3[0]
    df_axises3 = pd.DataFrame(df3.loc['datas','body'])
    df_axises3 = pd.DataFrame(df_axises3.loc[1,'values'])
    df_axises3 = df_axises3[0]
    df_pct_inflow = []
    for i in df_sales3: 
        try: 
            df_pct_inflow.append(float(i) / in_qty) 
        except ValueError: 
            df_pct_inflow.append(None)
    index3 = pd.RangeIndex(start=1, stop=len(df_axises3) + 1) 
    df_brand_inflow = pd.DataFrame({
        '品牌名': df_axises3,
        '流入人数(指数)': df_sales3,
        '人数占比': df_pct_inflow
    })
    df_brand_inflow = df_brand_inflow.sort_values(by='人数占比', ascending=False)
    df_brand_inflow.index = index3

    # 单品流入
    data4 = json.loads(json_str4)
    df4 = pd.DataFrame(data4)
    df_sales4 = pd.DataFrame(df4.loc['datas','body']) 
    df_sale4 = df_sales4.loc[2,'values']
    item_id4 = df_sales4.loc[0,'values']
    df_axise4 = pd.DataFrame(df4.loc['axises','body'])
    itemname4 = df_axise4.loc[1,'values']
    itembrand4 = df_axise4.loc[2,'values']
    df_pct4 = []
    for i in df_sale4: 
        try: 
            df_pct4.append(float(i) / in_qty) 
        except ValueError: 
            df_pct4.append(None)
    df_item_inflow_raw = pd.DataFrame({
        '单品': [item['key'] for item in itemname4], 
        '品牌': [brand['key'] for brand in itembrand4], 
        '流入人数': df_sale4,
        '人数占比': df_pct4,
        'ID': item_id4
    })
    df_item_inflow_raw = df_item_inflow_raw[df_item_inflow_raw['单品'] != '-']
    df_item_inflow_raw = df_item_inflow_raw.drop_duplicates(subset=['ID', '单品', '品牌'], keep='first')
    df_item_inflow_raw.index = pd.RangeIndex(start=1, stop=len(df_item_inflow_raw)+1)

    # 品牌净值
    def create_brand_net(inflow_df, outflow_df):
        min_inflow = min([float(x) for x in inflow_df['流入人数(指数)'] if pd.notna(x)])
        min_outflow = min([float(x) for x in outflow_df['流出人数(指数)'] if pd.notna(x)])
        all_brands = set(inflow_df['品牌名']).union(set(outflow_df['品牌名']))
        net_data = []
        for brand in all_brands:
            inflow_row = inflow_df[inflow_df['品牌名'] == brand]
            inflow_value = float(inflow_row['流入人数(指数)'].iloc[0]) if not inflow_row.empty else np.nan
            outflow_row = outflow_df[outflow_df['品牌名'] == brand]
            outflow_value = float(outflow_row['流出人数(指数)'].iloc[0]) if not outflow_row.empty else np.nan
            if pd.notna(inflow_value) and pd.notna(outflow_value):
                display_inflow = int(round(inflow_value))
                display_outflow = int(round(outflow_value))
                net_value = int(round(inflow_value - outflow_value))
                display_net = net_value
            elif pd.notna(inflow_value) and pd.isna(outflow_value):
                display_inflow = int(round(inflow_value))
                display_outflow = f"未进入TOP20(<{int(round(min_outflow))})"
                a = int(round(inflow_value - min_outflow))
                b = int(round(inflow_value))
                display_net = f"({a},{b})"
            elif pd.isna(inflow_value) and pd.notna(outflow_value):
                display_inflow = f"未进入TOP20(<{int(round(min_inflow))})"
                display_outflow = int(round(outflow_value))
                b = int(round(min_inflow - outflow_value))
                a = -int(round(outflow_value))
                display_net = f"({a},{b})"
            else:
                display_inflow = f"未进入TOP20(<{int(round(min_inflow))})"
                display_outflow = f"未进入TOP20(<{int(round(min_outflow))})"
                display_net = "N/A"
            net_data.append({
                '品牌名称': brand,
                '流入人数': display_inflow,
                '流失人数': display_outflow,
                '净值': display_net,
                '_inflow_value': inflow_value if pd.notna(inflow_value) else min_inflow - 1,
                '_outflow_value': outflow_value if pd.notna(outflow_value) else min_outflow - 1,
                '_net_value': (inflow_value - outflow_value) if (pd.notna(inflow_value) and pd.notna(outflow_value)) else np.nan
            })
        net_df = pd.DataFrame(net_data)
        net_brands = net_df[net_df['_net_value'].notna()].copy()
        net_brands = net_brands.sort_values(by=['_net_value', '_inflow_value'], ascending=[False, False])
        inflow_only = net_df[(net_df['_inflow_value'].notna()) & (net_df['_outflow_value'] == min_outflow - 1)].copy()
        inflow_only = inflow_only.sort_values(by='_inflow_value', ascending=False)
        outflow_only = net_df[(net_df['_outflow_value'].notna()) & (net_df['_inflow_value'] == min_inflow - 1)].copy()
        outflow_only = outflow_only.sort_values(by='_outflow_value', ascending=False)
        net_final = pd.concat([net_brands, inflow_only, outflow_only])
        net_final = net_final.drop(['_inflow_value', '_outflow_value', '_net_value'], axis=1)
        net_final.index = pd.RangeIndex(start=1, stop=len(net_final)+1)
        return net_final

    df_brand_net = create_brand_net(df_brand_inflow, df_brand_outflow)

    return df_brand_outflow, df_item_outflow_raw, df_brand_inflow, df_item_inflow_raw, df_brand_net

def compute_item_net_with_nickname(item_inflow, item_outflow, id_nickname_df):
    """
    使用映射表给单品匹配nickname，然后计算单品净值。
    返回：带nickname的流入df、流出df、单品净值df、未匹配的df
    """
    # 确保ID列类型一致
    item_inflow = item_inflow.copy()
    item_outflow = item_outflow.copy()
    item_inflow['ID'] = item_inflow['ID'].astype(str)
    item_outflow['ID'] = item_outflow['ID'].astype(str)
    id_nickname_df = id_nickname_df.copy()
    id_nickname_df['id'] = id_nickname_df['id'].astype(str)  # 注意列名为 'id'

    # 合并nickname（只取nickname列，忽略类目）
    nickname_map = id_nickname_df[['id', 'nickname']].rename(columns={'id':'ID'})
    inflow_merged = item_inflow.merge(nickname_map, on='ID', how='left')
    outflow_merged = item_outflow.merge(nickname_map, on='ID', how='left')
    # 调整列顺序
    inflow_merged = inflow_merged[['单品', '品牌', 'nickname', '流入人数', '人数占比', 'ID']]
    outflow_merged = outflow_merged[['单品', '品牌', 'nickname', '流出人数', '人数占比', 'ID']]
    inflow_merged.index = pd.RangeIndex(start=1, stop=len(inflow_merged)+1)
    outflow_merged.index = pd.RangeIndex(start=1, stop=len(outflow_merged)+1)

    # 找出未匹配的（nickname为NaN或'-'）
    unmatched_inflow = inflow_merged[inflow_merged['nickname'].isna() | (inflow_merged['nickname'] == '-')]
    unmatched_outflow = outflow_merged[outflow_merged['nickname'].isna() | (outflow_merged['nickname'] == '-')]
    unmatched_ids = pd.concat([
        unmatched_inflow[['ID', '单品', '品牌']],
        unmatched_outflow[['ID', '单品', '品牌']]
    ]).drop_duplicates(subset=['ID', '单品', '品牌'])
    # 标注数据来源
    unmatched_ids['数据来源'] = unmatched_ids.apply(
        lambda r: '流入' if r['ID'].isin(unmatched_inflow['ID']) and not r['ID'].isin(unmatched_outflow['ID'])
                  else ('流出' if r['ID'].isin(unmatched_outflow['ID']) and not r['ID'].isin(unmatched_inflow['ID'])
                        else '流入&流出'),
        axis=1
    )
    unmatched_ids = unmatched_ids[['ID', '单品', '品牌', '数据来源']]
    unmatched_ids.index = pd.RangeIndex(start=1, stop=len(unmatched_ids)+1)

    # 计算单品净值（按nickname汇总）
    inflow_clean = inflow_merged[~inflow_merged['nickname'].isna() & (inflow_merged['nickname'] != '-')]
    outflow_clean = outflow_merged[~outflow_merged['nickname'].isna() & (outflow_merged['nickname'] != '-')]
    inflow_sum = inflow_clean.groupby('nickname', as_index=False)['流入人数'].sum().rename(columns={'流入人数':'总流入人数'})
    outflow_sum = outflow_clean.groupby('nickname', as_index=False)['流出人数'].sum().rename(columns={'流出人数':'总流出人数'})
    merged = pd.merge(inflow_sum, outflow_sum, on='nickname', how='outer').fillna(np.nan)

    min_inflow = merged['总流入人数'].min() if not merged['总流入人数'].isna().all() else 0
    min_outflow = merged['总流出人数'].min() if not merged['总流出人数'].isna().all() else 0
    net_rows = []
    for _, row in merged.iterrows():
        nickname = row['nickname']
        if pd.isna(nickname) or nickname == '-':
            continue
        inflow_val = row['总流入人数'] if pd.notna(row['总流入人数']) else np.nan
        outflow_val = row['总流出人数'] if pd.notna(row['总流出人数']) else np.nan
        if pd.notna(inflow_val) and pd.notna(outflow_val):
            display_in = int(round(inflow_val))
            display_out = int(round(outflow_val))
            net = int(round(inflow_val - outflow_val))
            display_net = net
        elif pd.notna(inflow_val) and pd.isna(outflow_val):
            display_in = int(round(inflow_val))
            display_out = f"未进入TOP50(<{int(round(min_outflow))})"
            a = int(round(inflow_val - min_outflow))
            b = int(round(inflow_val))
            display_net = f"({a},{b})"
        elif pd.isna(inflow_val) and pd.notna(outflow_val):
            display_in = f"未进入TOP50(<{int(round(min_inflow))})"
            display_out = int(round(outflow_val))
            b = int(round(min_inflow - outflow_val))
            a = -int(round(outflow_val))
            display_net = f"({a},{b})"
        else:
            display_in = f"未进入TOP50(<{int(round(min_inflow))})"
            display_out = f"未进入TOP50(<{int(round(min_outflow))})"
            display_net = "N/A"
        net_rows.append({
            '单品名称': nickname,
            '总流入人数': display_in,
            '总流出人数': display_out,
            '净值': display_net,
            '_inflow_val': inflow_val if pd.notna(inflow_val) else min_inflow - 1,
            '_outflow_val': outflow_val if pd.notna(outflow_val) else min_outflow - 1,
            '_net_val': (inflow_val - outflow_val) if (pd.notna(inflow_val) and pd.notna(outflow_val)) else np.nan
        })
    net_df = pd.DataFrame(net_rows)
    if len(net_df) > 0:
        net_brands = net_df[net_df['_net_val'].notna()].copy()
        net_brands = net_brands.sort_values(by=['_net_val', '_inflow_val'], ascending=[False, False])
        inflow_only = net_df[(net_df['_inflow_val'].notna()) & (net_df['_outflow_val'] == min_outflow - 1)].copy()
        inflow_only = inflow_only.sort_values(by='_inflow_val', ascending=False)
        outflow_only = net_df[(net_df['_outflow_val'].notna()) & (net_df['_inflow_val'] == min_inflow - 1)].copy()
        outflow_only = outflow_only.sort_values(by='_outflow_val', ascending=False)
        net_final = pd.concat([net_brands, inflow_only, outflow_only])
        net_final = net_final.drop(['_inflow_val', '_outflow_val', '_net_val'], axis=1)
        net_final.index = pd.RangeIndex(start=1, stop=len(net_final)+1)
    else:
        net_final = pd.DataFrame(columns=['单品名称', '总流入人数', '总流出人数', '净值'])

    return inflow_merged, outflow_merged, net_final, unmatched_ids

# ---------- 加载默认映射表（如果未上传） ----------
def load_default_mapping():
    default_path = "data/竞品id匹配_0723updated.xlsx"
    if os.path.exists(default_path):
        try:
            df = pd.read_excel(default_path)
            # 检查必须列
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

# ---------- 主界面布局 ----------
with st.expander("📥 输入数据", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        outflow_qty = st.number_input("流失总人数 (outflow_qty)", min_value=1, value=1, step=1000, key="outflow_qty_input")
    with col2:
        inflow_qty = st.number_input("流入总人数 (inflow_qty)", min_value=1, value=1, step=1000, key="inflow_qty_input")
    
    # JSON文本框高度设为50
    json1 = st.text_area("📄 品牌流失 JSON", height=50, key="json1", placeholder="粘贴品牌流失的JSON数据...")
    json2 = st.text_area("📄 单品流失 JSON", height=50, key="json2", placeholder="粘贴单品流失的JSON数据...")
    json3 = st.text_area("📄 品牌流入 JSON", height=50, key="json3", placeholder="粘贴品牌流入的JSON数据...")
    json4 = st.text_area("📄 单品流入 JSON", height=50, key="json4", placeholder="粘贴单品流入的JSON数据...")

    st.markdown("**📎 上传 id-nickname 映射表 (Excel)**")
    st.caption("若不上传，将尝试从 data/id匹配_0723updated.xlsx 读取默认映射表。")
    uploaded_file = st.file_uploader("必须包含 'id', '类目', 'nickname' 三列", type=["xlsx"], key="mapping_upload")

    # 处理上传或默认加载
    if uploaded_file is not None:
        try:
            new_mapping = pd.read_excel(uploaded_file)
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
        # 如果还没有加载任何映射表，尝试加载默认
        if st.session_state.id_nickname_df is None:
            if load_default_mapping():
                st.success(f"已加载默认映射表 (data/id匹配_0723updated.xlsx)，共 {len(st.session_state.id_nickname_df)} 条记录。")
            # 否则显示提示（已在 load_default_mapping 中显示）

    # 显示当前映射表来源
    if st.session_state.id_nickname_df is not None:
        source = "上传" if st.session_state.mapping_source == 'uploaded' else "默认(data/id匹配_0723updated.xlsx)"
        st.info(f"✅ 当前映射表来源: {source}，共 {len(st.session_state.id_nickname_df)} 条记录。")

    run_btn = st.button("🚀 运行分析", type="primary")

# ---------- 执行计算 ----------
if run_btn:
    errors = []
    if not json1.strip():
        errors.append("品牌流失 JSON 不能为空")
    if not json2.strip():
        errors.append("单品流失 JSON 不能为空")
    if not json3.strip():
        errors.append("品牌流入 JSON 不能为空")
    if not json4.strip():
        errors.append("单品流入 JSON 不能为空")
    if outflow_qty <= 0:
        errors.append("流失总人数必须大于0")
    if inflow_qty <= 0:
        errors.append("流入总人数必须大于0")
    if st.session_state.id_nickname_df is None:
        errors.append("请先上传映射表或确保 data/id匹配_0723updated.xlsx 存在")

    if errors:
        for err in errors:
            st.error(err)
    else:
        try:
            # 解析JSON
            df_brand_out, df_item_out_raw, df_brand_in, df_item_in_raw, df_brand_net = parse_json_to_dfs(
                json1, json2, json3, json4, outflow_qty, inflow_qty
            )
            # 应用映射表匹配nickname
            inflow_merged, outflow_merged, df_item_net, unmatched = compute_item_net_with_nickname(
                df_item_in_raw, df_item_out_raw, st.session_state.id_nickname_df
            )

            # 保存原始df（用于后续更新映射时重新计算）
            st.session_state.raw_dfs = {
                'item_in_raw': df_item_in_raw,
                'item_out_raw': df_item_out_raw
            }

            st.session_state.computed_tables = {
                'df_brand_out': df_brand_out,
                'df_item_out': outflow_merged,
                'df_brand_in': df_brand_in,
                'df_item_in': inflow_merged,
                'df_brand_net': df_brand_net,
                'df_item_net': df_item_net,
                'unmatched': unmatched,
                'outflow_qty': outflow_qty,
                'inflow_qty': inflow_qty
            }
            st.session_state.unmatched_df = unmatched
            st.success("计算完成！请查看下方结果。")

        except json.JSONDecodeError as e:
            st.error(f"JSON 格式错误: {e}")
        except Exception as e:
            st.error(f"计算过程出错: {e}")
            st.exception(e)

# ---------- 显示结果 ----------
if st.session_state.computed_tables is not None:
    tables = st.session_state.computed_tables
    unmatched = tables['unmatched']

    # 如果有未匹配的，显示编辑区域
    if len(unmatched) > 0:
        st.subheader("⚠️ 发现未匹配的ID，请补充类目和nickname")
        st.info(f"共有 {len(unmatched)} 个ID未匹配到nickname。请在下方表格中为每个ID填写对应的「类目」和「nickname」，然后点击“更新映射并重新计算”。")

        # 构建编辑表格
        edit_df = unmatched[['ID', '单品', '品牌']].copy()
        # 初始化为空
        edit_df['类目'] = ""
        edit_df['nickname'] = ""

        # 如果之前有暂存编辑，则恢复
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
                "品牌": st.column_config.TextColumn("品牌", disabled=True),
                "类目": st.column_config.TextColumn("类目 (必填)", required=True),
                "nickname": st.column_config.TextColumn("nickname (必填)", required=True),
            },
            hide_index=True,
            use_container_width=True,
            key="edit_unmatched"
        )

        if st.button("🔄 更新映射并重新计算"):
            # 检查是否所有行都填了类目和nickname
            if edited['类目'].isna().any() or (edited['类目'] == '').any() or edited['nickname'].isna().any() or (edited['nickname'] == '').any():
                st.warning("请为所有ID填写完整的「类目」和「nickname」后再更新！")
            else:
                # 提取新映射
                new_mappings = edited[['ID', '类目', 'nickname']].copy()
                new_mappings['ID'] = new_mappings['ID'].astype(str)
                # 合并到现有映射表（若ID已存在则覆盖）
                current = st.session_state.id_nickname_df.copy()
                current['id'] = current['id'].astype(str)
                # 删除已存在的ID（用新数据覆盖）
                current = current[~current['id'].isin(new_mappings['ID'])]
                # 追加新数据
                updated = pd.concat([current, new_mappings.rename(columns={'ID':'id'})], ignore_index=True)
                # 按 类目, nickname 排序
                updated = updated.sort_values(by=['类目', 'nickname']).reset_index(drop=True)
                st.session_state.id_nickname_df = updated
                st.session_state.temp_nickname_edit = new_mappings  # 暂存本次编辑
                # 修改来源为 'uploaded'（因为现在映射是用户编辑的）
                st.session_state.mapping_source = 'uploaded'

                # 重新计算（使用保存的原始df）
                if st.session_state.raw_dfs is not None:
                    raw = st.session_state.raw_dfs
                    inflow_merged, outflow_merged, df_item_net, unmatched_new = compute_item_net_with_nickname(
                        raw['item_in_raw'], raw['item_out_raw'], updated
                    )
                    st.session_state.computed_tables['df_item_out'] = outflow_merged
                    st.session_state.computed_tables['df_item_in'] = inflow_merged
                    st.session_state.computed_tables['df_item_net'] = df_item_net
                    st.session_state.computed_tables['unmatched'] = unmatched_new
                    st.session_state.unmatched_df = unmatched_new
                    st.success("映射已更新并重新计算完成！请查看下方结果。")
                    st.rerun()
                else:
                    st.error("原始数据丢失，请重新运行分析。")

    # 展示所有表格
    st.subheader("📊 品牌流失 TOP20")
    st.dataframe(tables['df_brand_out'])

    st.subheader("🛍️ 单品流失 (含nickname)")
    st.dataframe(tables['df_item_out'])

    st.subheader("📊 品牌流入 TOP20")
    st.dataframe(tables['df_brand_in'])

    st.subheader("🛍️ 单品流入 (含nickname)")
    st.dataframe(tables['df_item_in'])

    st.subheader("⚖️ 品牌净值（流入−流出）")
    st.dataframe(tables['df_brand_net'].style.hide(axis="index"))

    st.subheader("⚖️ 单品净值（按nickname汇总）")
    st.dataframe(tables['df_item_net'].style.hide(axis="index"))

    # 如果所有已匹配，显示成功信息
    if len(unmatched) == 0:
        st.success("✅ 所有单品均已匹配到nickname！")

    # ---------- 下载最新的映射表 ----------
    if st.session_state.id_nickname_df is not None:
        st.markdown("---")
        st.subheader("📥 下载最新映射表")
        st.info("点击下方按钮可下载当前使用的完整映射表（包含所有已补充的 nickname），以便下次直接上传。")
        
        # 准备导出数据（包含三列）
        export_df = st.session_state.id_nickname_df.copy()
        # 确保列顺序为 id, 类目, nickname
        if 'id' not in export_df.columns:
            # 如果列名是 'ID'，则重命名
            export_df = export_df.rename(columns={'ID':'id'})
        export_df = export_df[['id', '类目', 'nickname']]
        # 按 类目, nickname 排序
        export_df = export_df.sort_values(by=['类目', 'nickname']).reset_index(drop=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='映射表')
        output.seek(0)
        st.download_button(
            label="📥 下载映射表 (Excel)",
            data=output,
            file_name="id_mapping_updated.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
