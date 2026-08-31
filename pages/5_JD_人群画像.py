import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import os
from datetime import datetime

st.set_page_config(page_title="JD_人群画像生成器", layout="wide")
st.title("📊 JD_人群画像生成器")

# 指定要保留的标签名（顺序将按此显示）
KEEP_TAGS = [
    "性别",
    "年龄",
    "城市线级",
    "购买力",
    "京享值",
    "十大靶群",
    "婚姻状况",
    "常用收货省份"
]

# ---------- 解析单个文件 ----------
def parse_population_file(file):
    """
    解析上传的 Excel 文件，返回 (人群名称, 数据字典)
    数据字典格式: {标签名: {枚举值: 占比}}
    """
    # 读取所有行（无表头）
    df_all = pd.read_excel(file, header=None, dtype=str)
    df_all = df_all.fillna('')  # 空值转空字符串

    # 1. 提取人群名称
    pop_name = None
    # 检查第一行第一列是否包含“人群=”
    first_cell = str(df_all.iloc[0, 0]).strip()
    if first_cell.startswith("人群="):
        pop_name = first_cell.split("=", 1)[1].strip()
    else:
        # 从文件名中提取：透视分析_之后的部分，去除扩展名
        base = os.path.basename(file.name)
        if "透视分析_" in base:
            pop_name = base.split("透视分析_", 1)[1].rsplit(".", 1)[0]
        else:
            pop_name = base.rsplit(".", 1)[0]  # 无前缀则用全名

    # 2. 定位表头行（查找包含"标签名"的行）
    header_row_idx = None
    for idx, row in df_all.iterrows():
        if any("标签名" in str(cell) for cell in row):
            header_row_idx = idx
            break
    if header_row_idx is None:
        raise ValueError("未找到表头行（包含'标签名'）")

    # 表头通常为 标签名, 枚举值, 占比, TGI
    # 数据从表头下一行开始
    data_rows = df_all.iloc[header_row_idx+1:].reset_index(drop=True)

    # 3. 解析数据
    tag_dict = {}          # {标签名: {枚举值: 占比}}
    current_tag = None

    for _, row in data_rows.iterrows():
        tag_cell = str(row[0]).strip()
        val_cell = str(row[1]).strip()
        pct_cell = str(row[2]).strip()

        # 如果标签名非空，更新当前标签
        if tag_cell != "":
            current_tag = tag_cell
            # 如果当前行有枚举值，也一并处理
            if val_cell != "" and pct_cell != "":
                try:
                    pct_val = float(pct_cell)
                except:
                    pct_val = np.nan
                if current_tag not in tag_dict:
                    tag_dict[current_tag] = {}
                tag_dict[current_tag][val_cell] = pct_val
            continue

        # 标签名为空，但枚举值和占比都有，则属于当前标签
        if val_cell != "" and pct_cell != "":
            if current_tag is None:
                continue  # 没有标签则忽略
            try:
                pct_val = float(pct_cell)
            except:
                pct_val = np.nan
            if current_tag not in tag_dict:
                tag_dict[current_tag] = {}
            tag_dict[current_tag][val_cell] = pct_val

    # 过滤出需要的标签
    filtered_dict = {}
    for tag in KEEP_TAGS:
        if tag in tag_dict:
            filtered_dict[tag] = tag_dict[tag]
        else:
            filtered_dict[tag] = {}   # 可能完全缺失

    return pop_name, filtered_dict


# ---------- 主界面 ----------
st.markdown("上传多个人群画像 Excel 文件，程序将提取指定标签并汇总成对比表格。")

uploaded_files = st.file_uploader(
    "📁 上传 Excel 文件（可多选）",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="支持 .xlsx 或 .xls 格式"
)

if uploaded_files and st.button("🚀 生成汇总"):
    # 存储所有人群的数据
    all_populations = {}  # {人群名称: {标签: {枚举值: 占比}}}
    all_enum_values = {}  # {标签: set(枚举值)}

    # 第一步：解析所有文件，同时收集所有枚举值
    progress_bar = st.progress(0)
    status_text = st.empty()
    for idx, file in enumerate(uploaded_files):
        status_text.text(f"正在解析: {file.name}")
        try:
            pop_name, tag_dict = parse_population_file(file)
        except Exception as e:
            st.error(f"解析文件 {file.name} 出错: {e}")
            continue
        all_populations[pop_name] = tag_dict
        # 收集枚举值
        for tag, enum_dict in tag_dict.items():
            if tag not in all_enum_values:
                all_enum_values[tag] = set()
            all_enum_values[tag].update(enum_dict.keys())
        progress_bar.progress((idx + 1) / len(uploaded_files))

    status_text.text("解析完成，正在构建汇总表...")

    if not all_populations:
        st.warning("没有成功解析任何文件，请检查文件格式。")
        st.stop()

    # 第二步：构建完整枚举值列表（按标签）
    tag_enum_map = {}
    for tag in KEEP_TAGS:
        if tag in all_enum_values:
            # 排序，对于数字型枚举值（如年龄区间）可能期望自然排序，但这里统一字符串排序
            enum_list = sorted(list(all_enum_values[tag]))
        else:
            enum_list = []
        tag_enum_map[tag] = enum_list

    # 第三步：构建DataFrame
    # 行索引: 标签名:枚举值
    rows = []
    for tag in KEEP_TAGS:
        enum_list = tag_enum_map.get(tag, [])
        if not enum_list:
            # 如果没有任何枚举值，添加一个占位行？但可能标签不存在，跳过
            continue
        for val in enum_list:
            rows.append(f"{tag}:{val}")

    # 创建空的DataFrame，索引为行标签，列为人群名称
    df_result = pd.DataFrame(index=rows, columns=list(all_populations.keys()))
    df_result = df_result.fillna(0.0)  # 初始为0

    # 填充数据
    for pop_name, tag_dict in all_populations.items():
        for tag, enum_dict in tag_dict.items():
            if tag not in KEEP_TAGS:
                continue
            for val, pct in enum_dict.items():
                row_key = f"{tag}:{val}"
                if row_key in df_result.index:
                    df_result.loc[row_key, pop_name] = pct

    # 将索引拆分为“标签名”和“枚举值”两列
    df_output = df_result.reset_index()
    # 拆分列
    df_output[["标签名", "枚举值"]] = df_output["index"].str.split(":", expand=True)
    # 删除原索引列
    df_output = df_output.drop(columns=["index"])
    # 重新排列列顺序
    cols = ["标签名", "枚举值"] + list(all_populations.keys())
    df_output = df_output[cols]

    # 按标签名排序（保持指定顺序）
    # 将标签名转为分类，按KEEP_TAGS顺序
    df_output["标签名"] = pd.Categorical(df_output["标签名"], categories=KEEP_TAGS, ordered=True)
    df_output = df_output.sort_values(["标签名", "枚举值"]).reset_index(drop=True)

    st.success(f"汇总完成！共 {len(all_populations)} 个人群。")

    # 显示表格
    st.subheader("📊 汇总对比表")
    st.dataframe(df_output, use_container_width=True)

    # 提供下载
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_output.to_excel(writer, index=False, sheet_name="汇总")
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="📥 下载汇总表 (Excel)",
        data=output,
        file_name=f"人群画像汇总_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("请上传至少一个 Excel 文件，然后点击生成汇总。")
