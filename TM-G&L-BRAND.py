import streamlit as st
import pandas as pd
import numpy as np
import json

# ---------- 数据处理函数 ----------
def compute_tables(json_str1, json_str2, json_str3, json_str4, out_qty, in_qty):
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
    index2 = pd.RangeIndex(start=1, stop=len(itemname) + 1) 
    df_item_outflow = pd.DataFrame({
        '单品': [item['key'] for item in itemname], 
        '品牌': [brand['key'] for brand in itembrand], 
        '流出人数': df_sale2,
        '人数占比': df_pct2,
        'ID': item_id
    })
    df_item_outflow.index = index2

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
    index4 = pd.RangeIndex(start=1, stop=len(itemname4) + 1) 
    df_item_inflow = pd.DataFrame({
        '单品': [item['key'] for item in itemname4], 
        '品牌': [brand['key'] for brand in itembrand4], 
        '流入人数': df_sale4,
        '人数占比': df_pct4,
        'ID': item_id4
    })
    df_item_inflow.index = index4

    # ---- 净值计算 ----
    def create_net_value_df(inflow_df, outflow_df):
        # 计算最小值（用于显示“未进入TOP20”）
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
        inflow_only_brands = net_df[(net_df['_inflow_value'].notna()) & (net_df['_outflow_value'] == min_outflow - 1)].copy()
        inflow_only_brands = inflow_only_brands.sort_values(by='_inflow_value', ascending=False)
        outflow_only_brands = net_df[(net_df['_outflow_value'].notna()) & (net_df['_inflow_value'] == min_inflow - 1)].copy()
        outflow_only_brands = outflow_only_brands.sort_values(by='_outflow_value', ascending=False)
        net_df_final = pd.concat([net_brands, inflow_only_brands, outflow_only_brands])
        net_df_final = net_df_final.drop(['_inflow_value', '_outflow_value', '_net_value'], axis=1)
        net_df_final.index = pd.RangeIndex(start=1, stop=len(net_df_final) + 1)
        return net_df_final

    df_brand_net = create_net_value_df(df_brand_inflow, df_brand_outflow)

    return df_brand_outflow, df_item_outflow, df_brand_inflow, df_item_inflow, df_brand_net


# ---------- Streamlit UI ----------
st.set_page_config(page_title="流入流出净值分析", layout="wide")
st.title("📊 品牌/商品流入流出净值分析")

st.markdown("请输入以下四段 JSON 数据（分别对应：品牌流失、商品流失、品牌流入、商品流入）以及总人数参数。")

# 参数输入
col1, col2 = st.columns(2)
with col1:
    outflow_qty = st.number_input("流失总人数 (outflow_qty)", value=0, step=1000, min_value=0)
with col2:
    inflow_qty = st.number_input("流入总人数 (inflow_qty)", value=0, step=1000, min_value=0)

# 四个 JSON 文本框（留空）
json1 = st.text_area("📄 品牌流失 JSON", height=25, placeholder="粘贴品牌流失的 JSON 数据...")
json2 = st.text_area("📄 商品流失 JSON", height=25, placeholder="粘贴商品流失的 JSON 数据...")
json3 = st.text_area("📄 品牌流入 JSON", height=25, placeholder="粘贴品牌流入的 JSON 数据...")
json4 = st.text_area("📄 商品流入 JSON", height=25, placeholder="粘贴商品流入的 JSON 数据...")

if st.button("运行分析", type="primary"):
    # 检查必填项
    errors = []
    if outflow_qty <= 0:
        errors.append("流失总人数必须大于0")
    if inflow_qty <= 0:
        errors.append("流入总人数必须大于0")
    if not json1.strip():
        errors.append("品牌流失 JSON 不能为空")
    if not json2.strip():
        errors.append("商品流失 JSON 不能为空")
    if not json3.strip():
        errors.append("品牌流入 JSON 不能为空")
    if not json4.strip():
        errors.append("商品流入 JSON 不能为空")
    
    if errors:
        for err in errors:
            st.error(err)
    else:
        try:
            with st.spinner("计算中..."):
                # 尝试解析 JSON 以提前发现格式错误
                json.loads(json1)
                json.loads(json2)
                json.loads(json3)
                json.loads(json4)
                # 调用计算
                df1, df2, df3, df4, df_net = compute_tables(
                    json1, json2, json3, json4, outflow_qty, inflow_qty
                )
        except json.JSONDecodeError as e:
            st.error(f"JSON 格式错误，请检查：{e}")
            st.stop()
        except Exception as e:
            st.error(f"计算过程出错：{e}")
            st.exception(e)
            st.stop()

        # 展示结果
        st.subheader("🏷️ 品牌流失 TOP20")
        st.dataframe(df1)

        st.subheader("🛍️ 单品流失 TOP50")
        st.dataframe(df2)

        st.subheader("🏷️ 品牌流入 TOP20")
        st.dataframe(df3)

        st.subheader("🛍️ 单品流入 TOP50")
        st.dataframe(df4)

        st.subheader("⚖️ 品牌净值（流入−流出）")
        st.dataframe(df_net.style.hide(axis="index"))
