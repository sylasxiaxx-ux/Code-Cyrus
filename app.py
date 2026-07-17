import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import shutil
from datetime import datetime

# 将你原有的核心逻辑封装成一个函数
def generate_portrait(folder_path, mapping_file, template_file):
    # 1. 读取映射表（原 try_3.0.xlsx）
    df_try = pd.read_excel(mapping_file)

    # 2. 遍历文件夹中的所有 .txt 文件
    for filename in os.listdir(folder_path):
        if not filename.endswith('.txt'):
            continue
        name = filename.replace('.txt', '').replace('-', '_')
        file_path = os.path.join(folder_path, filename)
        raw = pd.read_json(file_path)
        raw_new = raw.explode('snapshotResponseRegions')

        # 展开 tagValueResults
        result_df = pd.DataFrame()
        for index, row in raw_new.iterrows():
            rows_to_append = row['snapshotResponseRegions']['tagValueResults']
            result_df = pd.concat([result_df, pd.DataFrame(rows_to_append)], ignore_index=True)

        # 提取需要的三列
        result_df_final = pd.DataFrame({
            'tagName': result_df['tagEname'],
            'tagValueName': result_df['tagValueName'],
            'rate': result_df['rate']
        })

        # 替换英文标签名为中文（映射表）
        replace_map = {
            'cosmetics_year_cnt_region': '彩妆年消费频次',
            'skin_year_amt_region': '护肤年消费金额',
            'daas_tag_pred_gender': '性别',
            'common_receive_city_level_180d': '城市等级',
            'pref_purchasing_power': '购买力',
            'skin_year_cnt_region': '护肤年消费频次',
            'cosmetics_year_amt_region': '彩妆年消费金额',
            'daas_tag_pred_age_level': '年龄',
            'dkx_strategy_crowd': '策略人群',
            'derive_pay_ord_amt_6m_015_range': '月均消费金额',
            'daas_tag_label_name': '礼遇场景人群',
            'daas_tag_gift_label_name': '礼遇人群',
            'daas_tag_resident_city_tb_userid': '预测城市',
            'common_receive_province_180d': '预测省份',
            'daas_tag_cosmetic_market': '美妆洗护市场',
            'pref_beauty_skin': '肤质',
            'daas_tag_purchase_driven_factor_tag': '美妆心智人群',
            'daas_tag_trade_hour_most': '预测购买时间',
            'pref_skincare': '护肤品功效需求',
            'daas_tag_kx_crowd_name': '十大策略人群',
            'pref_cosmetics': '彩妆功效需求',
            'daas_tag_mz_seven_crowd': '美妆七大功效人群'
        }
        result_df_final['tagName'] = result_df_final['tagName'].replace(replace_map)
        # 特殊处理：性别、年龄（可能包含后缀）
        result_df_final.loc[result_df_final['tagName'].str.contains('daas_tag_pred_gender'), 'tagName'] = '性别'
        result_df_final.loc[result_df_final['tagName'].str.contains('daas_tag_pred_age_level'), 'tagName'] = '年龄'

        # 构造 A、B 两列（A = 标签名+数值名，B = rate）
        df10 = result_df_final[['tagName', 'tagValueName', 'rate']].copy()
        df10.columns = ['A', 'B', 'C']          # 临时重命名
        df10['A'] = df10['A'] + df10['B']      # 拼接
        df10['B'] = df10['C']
        df10.drop('C', axis=1, inplace=True)

        # 计算人群量级（购买力的 count 总和）
        ttl_df = result_df[result_df['tagEname'] == 'pref_purchasing_power']
        ttl = ttl_df['count'].sum() if not ttl_df.empty else 0
        ttl_row = pd.DataFrame([['人群量级', ttl]], columns=['A', 'B'])

        result_t = pd.concat([ttl_row, df10], ignore_index=True)
        result_t_deduplicated = result_t.groupby('A', as_index=False).first()

        # 左连接映射表
        df_try = pd.merge(df_try, result_t_deduplicated, how='left', on='A')
        df_try[name] = df_try['B']   # 以文件名作为列名

    # 3. 生成带时间戳的输出文件，并写入
    now = datetime.now()
    output_file = now.strftime("%Y%m%d_%H%M%S") + ".xlsx"
    shutil.copyfile(template_file, output_file)
    with pd.ExcelWriter(output_file, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_try.to_excel(writer, sheet_name="1", index=False)
    return output_file


# ------------------- Streamlit UI -------------------
st.set_page_config(page_title="人群画像生成器", layout="centered")
st.title("🧑‍🤝‍🧑 人群画像轻量生成器")

st.markdown("请选择以下文件/文件夹路径，点击运行即可生成新的人群画像 Excel 文件。")

with st.form("input_form"):
    folder_path = st.text_input("📁 JSON 文件所在文件夹路径（绝对路径）", 
                                placeholder="例如：C:/Users/xxx/画像txt")
    mapping_file = st.text_input("📄 映射表文件路径（try_3.0.xlsx）", 
                                 placeholder="例如：C:/Users/xxx/try_3.0.xlsx")
    template_file = st.text_input("📄 模板文件路径（多人群画像_模板_3.0.xlsx）",
                                  placeholder="例如：C:/Users/xxx/多人群画像_模板_3.0.xlsx")
    submitted = st.form_submit_button("🚀 开始生成画像")

if submitted:
    if not all([folder_path, mapping_file, template_file]):
        st.error("请完整填写所有路径！")
    elif not os.path.isdir(folder_path):
        st.error("JSON 文件夹路径不存在，请检查！")
    elif not os.path.isfile(mapping_file):
        st.error("映射表文件不存在，请检查！")
    elif not os.path.isfile(template_file):
        st.error("模板文件不存在，请检查！")
    else:
        with st.spinner("正在处理，请稍候..."):
            try:
                out_file = generate_portrait(folder_path, mapping_file, template_file)
                st.success(f"✅ 生成成功！文件名为：{out_file}")
                with open(out_file, "rb") as f:
                    st.download_button(
                        label="📥 点击下载结果 Excel",
                        data=f,
                        file_name=out_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            except Exception as e:
                st.error(f"运行出错：{e}")
