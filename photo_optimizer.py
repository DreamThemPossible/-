import streamlit as st
from PIL import Image
import os
import numpy as np
# 导入火山方舟官方SDK
from volcenginesdkarkruntime import Ark

# 页面基础配置
st.set_page_config(page_title="风景打卡照拍摄指导助手", page_icon="📸", layout="wide")

# 密钥文件路径（和代码同目录）
KEY_FILE_PATH = "DOUBAO_API_KEY.txt"

# ---------------------- 核心配置：100+风景打卡照关键词（分类） ----------------------
ACTION_KEYWORDS = {
    "风格类": [
        "帅气", "活力", "安静", "氛围感", "治愈", "清新", "文艺", "复古", "日系", "韩系",
        "港风", "ins风", "森系", "盐系", "甜系", "酷飒", "温柔", "慵懒", "元气", "松弛感",
        "高级感", "电影感", "故事感", "少女感", "少年感", "清冷感", "温暖", "随性", "简约", "时尚"
    ],
    "动作类": [
        "抬手比耶", "插兜站立", "歪头微笑", "侧身回头", "蹲下抓拍", "行走抓拍", "倚靠树干",
        "坐在草地", "眺望远方", "抬手撩发", "双手张开", "低头浅笑", "仰头看天", "扶帽子", "托腮思考",
        "比心", "捂嘴笑", "伸懒腰", "跳跃抓拍", "盘腿坐", "背靠大树", "手插口袋", "摸耳朵",
        "咬嘴唇", "挥手打招呼", "假装走路", "整理衣角", "撑伞站立", "捧花拍照", "吹泡泡", "喂鸽子"
    ],
    "视角类": [
        "平视", "微仰", "微俯", "低角度", "高角度", "侧面视角", "背影视角", "特写", "远景",
        "中景", "仰拍天空", "俯拍地面", "对角线构图", "三分法构图", "对称构图", "引导线构图",
        "前景虚化", "背景虚化", "逆光拍摄", "侧光拍摄", "顺光拍摄", "黄金分割点"
    ],
    "氛围类": [
        "日落时分", "清晨薄雾", "午后阳光", "黄昏光影", "雨夜氛围", "星空背景", "花海环绕",
        "海边微风", "森林光影", "麦田微风", "湖边倒影", "山路蜿蜒", "古城街巷", "草原辽阔",
        "雪山背景", "云海翻涌", "枫叶飘落", "樱花飞舞", "芦苇飘荡", "波光粼粼", "落叶满地"
    ]
}

# 扁平化所有关键词（用于搜索）
ALL_KEYWORDS = [kw for cat in ACTION_KEYWORDS.values() for kw in cat]

# ---------------------- 核心功能1：读取密钥文件 ----------------------
def load_api_keys_from_file(file_path):
    """从txt文件读取API密钥，仅保留AK和MODEL_ID"""
    api_config = {
        "ACCESS_KEY_ID": "",  # 对应SDK的api_key
        "MODEL_ID": ""
    }
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        st.error(f"❌ 密钥文件不存在！请检查路径：{file_path}")
        st.info("💡 请在代码同目录下创建DOUBAO_API_KEY.txt，按格式写入：\nACCESS_KEY_ID=你的AK\nMODEL_ID=你的模型ID")
        return api_config
    
    # 读取文件并解析
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key in api_config:
                        api_config[key] = value
        
        # 校验必填项
        empty_fields = [k for k, v in api_config.items() if not v]
        if empty_fields:
            st.error(f"❌ 密钥文件中以下字段为空：{', '.join(empty_fields)}")
        
        st.success("✅ 密钥文件读取成功！")
        return api_config
    except Exception as e:
        st.error(f"❌ 读取密钥文件失败：{str(e)}")
        return api_config

# ---------------------- 核心功能2：轻量背景识别（无需YOLO） ----------------------
def analyze_background_light(image):
    """轻量背景识别：基于色彩/纹理判断风景类型"""
    # 转换为numpy数组
    img_np = np.array(image.convert("RGB"))
    # 获取色彩特征（主色调）
    avg_r = np.mean(img_np[:, :, 0])
    avg_g = np.mean(img_np[:, :, 1])
    avg_b = np.mean(img_np[:, :, 2])
    
    # 获取图像亮度
    brightness = (avg_r + avg_g + avg_b) / 3
    
    # 背景类型判断
    background = "通用风景"
    # 绿色占比高 → 森林/草地
    if avg_g > avg_r and avg_g > avg_b:
        background = "森林/草地"
    # 蓝色占比高 → 海边/湖泊/天空
    elif avg_b > avg_r and avg_b > avg_g:
        if brightness > 200:
            background = "晴朗天空/海边"
        else:
            background = "湖泊/阴天海边"
    # 暖色调（红/黄）→ 日落/古城/沙漠
    elif avg_r > avg_g and avg_r > avg_b:
        background = "日落/古城/沙漠"
    # 亮度低 → 夜景/树林深处
    elif brightness < 100:
        background = "夜景/树林深处"
    
    # 图像尺寸和比例
    width, height = image.size
    aspect_ratio = round(width / height, 2)
    
    return {
        "background_type": background,
        "aspect_ratio": aspect_ratio,
        "brightness": brightness,
        "width": width,
        "height": height
    }

# ---------------------- 核心功能3：调用官方SDK生成图片 ----------------------
def generate_image_with_ark_sdk(prompt, model_id, ak):
    """使用火山方舟官方SDK生成图片"""
    try:
        # 初始化SDK客户端
        client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=ak
        )
        
        # 调用文生图接口
        images_response = client.images.generate(
            model=model_id,
            prompt=prompt,
            size="2K",
            response_format="url",
            watermark=False
        )
        
        return images_response.data[0].url
    except Exception as e:
        st.error(f"❌ 调用官方SDK失败：{str(e)}")
        st.info("💡 请检查：1. API Key是否正确 2. 模型ID是否存在 3. 网络是否正常")
        return None

# ---------------------- 核心功能4：生成个性化提示词 ----------------------
def generate_custom_prompt(selected_keywords, custom_prompt_text, background_info):
    """结合用户选择的关键词+自定义提示词+背景信息，生成精准提示词"""
    # 拆分用户选择的关键词（按分类）
    style_kw = [kw for kw in selected_keywords if kw in ACTION_KEYWORDS["风格类"]]
    action_kw = [kw for kw in selected_keywords if kw in ACTION_KEYWORDS["动作类"]]
    view_kw = [kw for kw in selected_keywords if kw in ACTION_KEYWORDS["视角类"]]
    atmosphere_kw = [kw for kw in selected_keywords if kw in ACTION_KEYWORDS["氛围类"]]
    
    # 基础提示词
    base_prompt = f"""
    生成一张风景打卡照拍摄指导样例图（卡通风格）：
    1. 背景环境：{background_info['background_type']}，保留真实背景的核心特征，色调自然；
    2. 人物形象：卡通风格人物（圆脸、大眼睛、简约线条），比例协调，融入背景；
    3. 整体风格：{', '.join(style_kw) if style_kw else '清新自然'}；
    4. 人物动作：{', '.join(action_kw) if action_kw else '自然站立，微笑看向镜头'}；
    5. 拍摄视角/构图：{', '.join(view_kw) if view_kw else '三分法构图，平视角度'}；
    6. 氛围/光影：{', '.join(atmosphere_kw) if atmosphere_kw else '自然光影，氛围感拉满'}；
    7. 自定义要求：{custom_prompt_text if custom_prompt_text else '无额外要求'}；
    8. 画面要求：高清分辨率，无水印，构图美观，动作清晰，能直接指导真人模仿拍摄；
    9. 卡通风格：日系简约卡通，线条清晰，色彩明亮，人物动作辨识度高。
    """
    
    return base_prompt.strip()

# ---------------------- 主界面 ----------------------
def main():
    st.title("📸 风景打卡照拍摄指导助手")
    st.subheader("选择动作关键词 → 输入自定义描述 → 上传背景 → 点击生成 → 模仿拍摄")
    
    # 第一步：读取密钥文件
    api_config = load_api_keys_from_file(KEY_FILE_PATH)
    ak = api_config["ACCESS_KEY_ID"]
    model_id = api_config["MODEL_ID"]
    
    # 校验核心字段
    if not ak or not model_id:
        st.stop()
    
    # 第二步：关键词选择区（支持检索）
    st.markdown("### 📝 选择打卡照关键词（可搜索/多选）")
    # 关键词搜索框
    search_kw = st.text_input("🔍 搜索关键词（如：帅气、抬手比耶、微仰）", placeholder="输入关键词后回车")
    
    # 筛选关键词（搜索匹配）
    filtered_keywords = []
    if search_kw:
        filtered_keywords = [kw for kw in ALL_KEYWORDS if search_kw in kw]
    else:
        filtered_keywords = ALL_KEYWORDS
    
    # 分类展示关键词（带复选框）
    selected_keywords = []
    st.markdown("#### 📚 关键词分类选择")
    for cat, kws in ACTION_KEYWORDS.items():
        st.markdown(f"**{cat}**")
        # 筛选当前分类下的匹配关键词（修正语法错误）
        cat_filtered = [kw for kw in kws if search_kw in kw] if search_kw else kws
        # 每行显示6个关键词
        cols = st.columns(6)
        for i, kw in enumerate(cat_filtered):
            with cols[i % 6]:
                if st.checkbox(kw, key=f"kw_{kw}"):
                    selected_keywords.append(kw)
    
    # 显示已选关键词
    if selected_keywords:
        st.success(f"✅ 已选择关键词：{', '.join(selected_keywords)}")
    else:
        st.warning("⚠️ 请至少选择1个关键词（风格/动作/视角/氛围）")
    
    # 新增：自定义提示词输入框
    st.markdown("### ✏️ 自定义提示词（补充个性化要求）")
    custom_prompt_text = st.text_area(
        "输入额外的拍摄要求（如：戴白色帽子、手里拿咖啡杯、穿牛仔外套等）",
        placeholder="例：戴米色贝雷帽，手里拿着气球，脚踩石头",
        height=100
    )
    
    st.divider()
    
    # 第三步：上传照片
    uploaded_file = st.file_uploader(
        "📷 上传风景打卡背景照片（JPG/PNG）",
        type=["jpg", "png"],
        help="上传包含风景背景的照片（如海边、森林、草地等）"
    )
    
    # 新增：生成按钮（核心）
    st.markdown("### 🚀 生成拍摄样例")
    generate_btn = st.button("点击生成卡通拍摄样例", type="primary", use_container_width=True)
    
    # 第四步：点击生成按钮后执行逻辑
    if generate_btn:
        # 前置校验
        if not selected_keywords:
            st.error("❌ 请先选择至少1个关键词（风格/动作/视角/氛围）！")
            st.stop()
        if uploaded_file is None:
            st.error("❌ 请先上传风景背景照片！")
            st.stop()
        
        # 展示上传的照片
        st.markdown("### 📷 你的打卡背景照片")
        image = Image.open(uploaded_file)
        st.image(image, caption="原始背景照片", use_column_width=True)
        
        # 轻量分析背景
        with st.spinner("🔍 正在分析背景类型（森林/海边/日落等）..."):
            background_info = analyze_background_light(image)
        
        # 展示背景分析结果
        st.markdown("### 📊 背景分析结果")
        st.write(f"• 背景类型：{background_info['background_type']}")
        st.write(f"• 画面比例（宽/高）：{background_info['aspect_ratio']}")
        st.write(f"• 画面亮度：{'明亮' if background_info['brightness'] > 150 else '柔和' if background_info['brightness'] > 100 else '偏暗'}")
        
        # 生成个性化提示词（整合自定义提示词）
        with st.spinner("✍️ 正在生成专属拍摄提示词..."):
            custom_prompt = generate_custom_prompt(selected_keywords, custom_prompt_text, background_info)
        
        # 展示提示词
        with st.expander("📝 查看生成的提示词（可修改）", expanded=False):
            st.text_area("提示词内容", custom_prompt, height=200)
        
        # 生成卡通样例
        with st.spinner("🎨 正在生成卡通拍摄指导样例...（约20秒）"):
            sample_url = generate_image_with_ark_sdk(custom_prompt, model_id, ak)
        
        # 展示样例和拍摄指导
        st.divider()
        st.markdown("### 🎨 打卡照拍摄指导样例（卡通版）")
        if sample_url:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.image(sample_url, caption="卡通拍摄样例（可模仿动作/视角）", use_column_width=True)
            with col2:
                st.markdown("#### 💡 拍摄指导建议")
                st.write(f"1. 动作模仿：{', '.join([kw for kw in selected_keywords if kw in ACTION_KEYWORDS['动作类']]) or '自然站立微笑'}")
                st.write(f"2. 视角选择：{', '.join([kw for kw in selected_keywords if kw in ACTION_KEYWORDS['视角类']]) or '平视+三分法构图'}")
                st.write(f"3. 风格参考：{', '.join([kw for kw in selected_keywords if kw in ACTION_KEYWORDS['风格类']]) or '清新自然'}")
                st.write(f"4. 自定义要求：{custom_prompt_text if custom_prompt_text else '无'}")
                st.write(f"5. 适配背景：{background_info['background_type']}，建议在该场景下拍摄")
                st.write(f"6. 光影建议：{'顺光拍摄' if background_info['brightness'] > 150 else '侧光拍摄增强层次'}")
        else:
            st.error("❌ 拍摄样例生成失败，请检查API配置或网络")

# 程序入口
if __name__ == "__main__":
    main()