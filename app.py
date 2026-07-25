import streamlit as st
import tempfile
from openai import OpenAI
import camelot

###### unuse func #####
def extract_text_from_pdf(file):
    """提取PDF文本内容（非表格部分）"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        doc = fitz.open(tmp_path)
        text_content = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            text_content.append({
                'page': page_num + 1,
                'content': text
            })
        
        doc.close()
        return text_content, tmp_path
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def extract_images_from_pdf(file):
    """提取PDF中的图片（可用于图表分析）"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        doc = fitz.open(tmp_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                images.append({
                    'page': page_num + 1,
                    'index': img_index,
                    'image': Image.open(io.BytesIO(image_bytes))
                })
        
        doc.close()
        return images
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

def init_session_state():
    """初始化会话状态"""
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    
    if 'favorite_analyses' not in st.session_state:
        st.session_state.favorite_analyses = []
    
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None

def save_analysis_record(question, answer, files_info, mode, model):
    """保存分析记录"""
    record = {
        'id': datetime.now().strftime("%Y%m%d_%H%M%S"),
        'timestamp': datetime.now().isoformat(),
        'question': question,
        'answer': answer,
        'files': [f['name'] for f in files_info],
        'mode': mode,
        'model': model,
        'is_favorite': False
    }
    st.session_state.analysis_history.append(record)
    return record['id']

def export_history_to_json():
    """导出历史记录为JSON"""
    if not st.session_state.analysis_history:
        return None
    
    export_data = {
        'export_date': datetime.now().isoformat(),
        'total_records': len(st.session_state.analysis_history),
        'records': st.session_state.analysis_history
    }
    
    return json.dumps(export_data, ensure_ascii=False, indent=2)

def render_history_sidebar():
    """在侧边栏显示分析历史"""
    st.sidebar.header("📚 分析历史")
    
    if not st.session_state.analysis_history:
        st.sidebar.info("暂无分析记录")
        return
    
    # 搜索和过滤历史记录
    search_term = st.sidebar.text_input("🔍 搜索历史记录", key="history_search")
    
    filtered_history = st.session_state.analysis_history[::-1]
    if search_term:
        filtered_history = [
            h for h in filtered_history 
            if search_term.lower() in h['question'].lower() 
            or search_term.lower() in h['answer'].lower()
        ]
    
    # 显示历史记录数量
    st.sidebar.markdown(f"**共 {len(filtered_history)} 条记录**")
    
    # 导出按钮
    if st.sidebar.button("📥 导出历史记录"):
        json_data = export_history_to_json()
        if json_data:
            st.sidebar.download_button(
                "下载JSON文件",
                json_data,
                file_name=f"analysis_history_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    st.sidebar.markdown("---")
    
    # 显示每条历史记录
    for item in filtered_history[:5]:  # 只显示最近5条
        with st.sidebar.expander(f"📝 {item['question'][:30]}..."):
            st.markdown(f"**时间:** {item['timestamp']}")
            st.markdown(f"**文件:** {', '.join(item['files'])}")
            st.markdown(f"**模式:** {item['mode']}")
            st.markdown(f"**模型:** {item['model']}")
            
            if st.button(f"⭐ {'取消收藏' if item['is_favorite'] else '收藏'}", key=f"fav_{item['id']}"):
                item['is_favorite'] = not item['is_favorite']
                if item['is_favorite']:
                    st.session_state.favorite_analyses.append(item)
                else:
                    st.session_state.favorite_analyses = [
                        f for f in st.session_state.favorite_analyses 
                        if f['id'] != item['id']
                    ]
                st.rerun()

def compare_model_responses(api_key, base_url, question, tables_data, models_to_test):
    """对比不同模型的回答"""
    results = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, model in enumerate(models_to_test):
        status_text.text(f"正在测试模型: {model}")
        
        start_time = time.time()
        try:
            prompt = build_prompt_for_multiple(question, tables_data)
            answer = call_llm(api_key, base_url, model, prompt)
            elapsed_time = time.time() - start_time
            
            results[model] = {
                'answer': answer,
                'time': elapsed_time,
                'success': True,
                'error': None
            }
        except Exception as e:
            results[model] = {
                'answer': None,
                'time': time.time() - start_time,
                'success': False,
                'error': str(e)
            }
        
        progress_bar.progress((i + 1) / len(models_to_test))
    
    status_text.empty()
    progress_bar.empty()
    
    return results

def render_model_comparison(results):
    """渲染模型对比结果"""
    if not results:
        return
    
    st.subheader("🤖 模型对比结果")
    
    # 性能对比表
    comparison_data = []
    for model, result in results.items():
        comparison_data.append({
            '模型': model,
            '响应时间': f"{result['time']:.2f}秒",
            '状态': '✅ 成功' if result['success'] else '❌ 失败',
            '回答长度': len(result['answer']) if result['answer'] else 0
        })
    
    if comparison_data:
        df_comparison = pd.DataFrame(comparison_data)
        st.dataframe(df_comparison, use_container_width=True)
        
        # 可视化对比
        col1, col2 = st.columns(2)
        
        with col1:
            # 响应时间柱状图
            time_data = {
                '模型': [r['模型'] for r in comparison_data],
                '响应时间(秒)': [float(r['响应时间'].replace('秒', '')) for r in comparison_data]
            }
            df_time = pd.DataFrame(time_data)
            st.bar_chart(df_time.set_index('模型'))
        
        with col2:
            # 回答长度柱状图
            length_data = {
                '模型': [r['模型'] for r in comparison_data],
                '回答长度(字符)': [r['回答长度'] for r in comparison_data]
            }
            df_length = pd.DataFrame(length_data)
            st.bar_chart(df_length.set_index('模型'))
    
    # 显示每个模型的详细回答
    st.markdown("---")
    st.subheader("📝 详细回答对比")
    
    model_tabs = st.tabs(list(results.keys()))
    for tab, (model, result) in zip(model_tabs, results.items()):
        with tab:
            if result['success']:
                st.markdown(f"**响应时间:** {result['time']:.2f}秒")
                st.markdown("**回答:**")
                st.markdown(result['answer'])
            else:
                st.error(f"**错误:** {result['error']}")

def export_results(results, format_type="markdown"):
    """支持多种格式导出结果"""
    if format_type == "markdown":
        return results
    
    elif format_type == "json":
        data = {
            "analysis_date": datetime.now().isoformat(),
            "results": results
        }
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    elif format_type == "csv":
        # 简单CSV导出
        lines = ["Question,Answer"]
        lines.append(f'"{results.get("question", "")}","{results.get("answer", "")}"')
        return "\n".join(lines)
    
    elif format_type == "html":
        # 转换为HTML格式
        html_content = f"""
        <html>
        <head><meta charset="utf-8"><title>分析结果</title></head>
        <body>
            <h1>分析结果</h1>
            <p><strong>时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <div>{markdown.markdown(results)}</div>
        </body>
        </html>
        """
        return html_content

def generate_analysis_report(question, all_results, metadata_list, model_info):
    """生成综合PDF报告"""
    
    class AnalysisReport(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, '循证医学分析报告', 0, 1, 'C')
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(10)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')
    
    pdf = AnalysisReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # 添加中文字体支持（需要中文字体文件）
    # pdf.add_font('SimSun', '', 'simsun.ttf', uni=True)
    # pdf.set_font('SimSun', '', 12)
    
    # 报告头部信息
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Analysis Report', 0, 1, 'C')
    pdf.ln(10)
    
    # 基本信息
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
    pdf.cell(0, 10, f'Model: {model_info}', 0, 1)
    pdf.cell(0, 10, f'Question: {question}', 0, 1)
    pdf.ln(10)
    
    # 文献元数据
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Literature Metadata', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    for meta in metadata_list:
        pdf.cell(0, 10, f"File: {meta.get('file_name', 'N/A')}", 0, 1)
        pdf.cell(0, 10, f"Pages: {meta.get('pages', 'N/A')}", 0, 1)
        pdf.cell(0, 10, f"Author: {meta.get('author', 'N/A')}", 0, 1)
        pdf.ln(5)
    
    # 分析结果
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Analysis Results', 0, 1)
    pdf.set_font('Arial', '', 10)
    
    for result in all_results:
        pdf.multi_cell(0, 10, result)
        pdf.ln(5)
    
    # 保存到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        pdf.output(tmp_file.name)
        tmp_path = tmp_file.name
    
    return tmp_path

def analyze_pdf_metadata(file):
    """分析PDF元数据和质量"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_path = tmp_file.name
    
    try:
        doc = fitz.open(tmp_path)
        metadata = {
            'file_name': file.name,
            'file_size': f"{file.size / 1024:.2f} KB",
            'pages': len(doc),
            'title': doc.metadata.get('title', 'N/A'),
            'author': doc.metadata.get('author', 'N/A'),
            'subject': doc.metadata.get('subject', 'N/A'),
            'keywords': doc.metadata.get('keywords', 'N/A'),
            'creation_date': doc.metadata.get('creationDate', 'N/A'),
            'has_text_layer': False,
            'has_tables': False,
            'table_count': 0
        }
        
        # 检查是否有文本层
        for page in doc:
            if page.get_text().strip():
                metadata['has_text_layer'] = True
                break
        
        doc.close()
        return metadata
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)



# 这里填入你自己的 OpenAI API key
client = OpenAI(
    api_key='sk-xT4H5qIik5ua5jAFMVwSB06vnGT6RzmXxJK8eFP9EDzw13L2',
    base_url="https://api.hunyuan.cloud.tencent.com/v1",  # 混元 endpoint
    )

st.title("📄循证医学智能体平台")

uploaded_file = st.file_uploader("上传 PDF", type="pdf")
question = st.text_input("输入你的问题，例如：提取临床数据中的表格信息")

if uploaded_file and question:
    # 尝试提取所有表格，使用 lattice 模式（适合有框线的表格，常见于论文）
    # 使用临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.getvalue())
        tmp_path = tmp_file.name
    tables = camelot.read_pdf(tmp_path, flavor='stream', pages='all')
    print(f"read table num {len(tables)}")
    # 将所有表格数据转换为文本格式，供LLM使用
    tables_text = ""
    for i, table in enumerate(tables):
        # # 获取表格的DataFrame
        df = table.df
        # # fliter text info
        if(len(df.shape) >= 2 and df.shape[1] > 2):
            # print(f"table {i} table {df.to_string(index=False, header=True)}")
            # tables_text += df.to_string(index=False, header=True)
            tables_text += df.to_markdown(index=False)
    # print(tables_text)
    # 调用 LLM 提取答案
    prompt = f"""
    {question}，参考以下文献：
    {tables_text}
    """
    print(f"token len {len(prompt)}")
    # 新的API调用方式
    resp = client.chat.completions.create(
        model="hunyuan-turbos-latest",
        messages=[{"role":"user", "content": prompt}]
    )
    st.subheader("📊 答案：")

    st.write(resp.choices[0].message.content)
