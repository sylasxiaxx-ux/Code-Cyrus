import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
import os
from datetime import datetime

st.set_page_config(page_title="Excel 合并工具", layout="wide")
st.title("📂 Excel 合并工具")

st.markdown("上传多个 Excel 文件，将它们的 sheet 合并到一个文件中。")

# ---------- 缓存上传的文件 ----------
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# ---------- 上传区域 ----------
uploaded_files = st.file_uploader(
    "📁 上传 Excel 文件（可多选）",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    help="支持 .xlsx 和 .xls 格式"
)

if uploaded_files:
    st.session_state.uploaded_files = uploaded_files

# ---------- 合并选项 ----------
if st.session_state.uploaded_files:
    merge_mode = st.radio(
        "选择合并方式",
        options=["纵向合并所有数据（所有 sheet 按行拼接）", "按 sheet 合并（每个 sheet 独立）"],
        index=0,
        help="纵向合并：所有文件的所有 sheet 按行拼接成一个 sheet（要求列结构一致）。按 sheet 合并：每个 sheet 独立保留，合并到一个工作簿。"
    )

    # 显示上传文件列表
    with st.expander("📋 已上传文件", expanded=False):
        for f in st.session_state.uploaded_files:
            st.write(f"- {f.name} ({f.size} bytes)")

    if st.button("🚀 开始合并", type="primary"):
        all_dfs = []
        sheet_names = []
        file_count = 0

        progress_bar = st.progress(0)
        status_text = st.empty()
        total_files = len(st.session_state.uploaded_files)

        if merge_mode.startswith("纵向"):
            # 纵向合并模式：读取所有 sheet 并拼接
            combined_df = pd.DataFrame()
            for idx, file in enumerate(st.session_state.uploaded_files):
                status_text.text(f"正在读取: {file.name}")
                try:
                    xls = pd.ExcelFile(file)
                    for sheet in xls.sheet_names:
                        df = pd.read_excel(file, sheet_name=sheet, header=0)
                        # 跳过空 DataFrame
                        if not df.empty:
                            combined_df = pd.concat([combined_df, df], ignore_index=True)
                except Exception as e:
                    st.error(f"读取 {file.name} 出错: {e}")
                    continue
                progress_bar.progress((idx + 1) / total_files)

            if combined_df.empty:
                st.warning("没有有效数据可合并。")
                st.stop()

            # 显示预览
            st.subheader("📊 预览合并结果（前100行）")
            st.dataframe(combined_df.head(100), use_container_width=True)

            # 提供下载
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                combined_df.to_excel(writer, index=False, sheet_name="合并数据")
            output.seek(0)

            st.success(f"合并完成！共 {len(combined_df)} 行数据。")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 下载合并后的 Excel",
                data=output,
                file_name=f"合并结果_纵向_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            # 按 sheet 合并：每个 sheet 独立保留
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for idx, file in enumerate(st.session_state.uploaded_files):
                    status_text.text(f"正在处理: {file.name}")
                    try:
                        xls = pd.ExcelFile(file)
                        for sheet in xls.sheet_names:
                            df = pd.read_excel(file, sheet_name=sheet, header=0)
                            if df.empty:
                                continue
                            # 生成唯一的 sheet 名
                            base_name = f"{os.path.splitext(file.name)[0]}_{sheet}"
                            # 如果 sheet 名过长或包含非法字符，简化处理
                            sheet_name_safe = base_name.replace("/", "_").replace("\\", "_")[:31]  # Excel 限制31字符
                            # 确保唯一性
                            counter = 1
                            orig = sheet_name_safe
                            while sheet_name_safe in writer.sheets:
                                sheet_name_safe = f"{orig}_{counter}"
                                counter += 1
                            df.to_excel(writer, sheet_name=sheet_name_safe, index=False)
                    except Exception as e:
                        st.error(f"处理 {file.name} 出错: {e}")
                        continue
                    progress_bar.progress((idx + 1) / total_files)

            output.seek(0)
            st.success("合并完成！所有 sheet 已合并到一个工作簿。")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="📥 下载合并后的 Excel",
                data=output,
                file_name=f"合并结果_按sheet_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # 显示 sheet 列表
            st.subheader("📋 生成的 sheet 列表")
            with pd.ExcelFile(output) as xls:
                st.write("\n".join(xls.sheet_names))

        status_text.empty()
        progress_bar.empty()

else:
    st.info("请上传至少一个 Excel 文件。")
