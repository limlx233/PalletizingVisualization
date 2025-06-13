import io
import time
import base64
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


# 设置页面和字体
st.set_page_config(
    page_title="纵横式码垛方案可视化",
    page_icon="📦",
    layout="centered",
    initial_sidebar_state="expanded"
)

import matplotlib.font_manager as fm
# 添加字体搜索路径
font_path = "font/MSYH.TTC"
fm.fontManager.addfont(font_path)
# 设置使用该字体
plt.rcParams['font.family'] = 'Microsoft YaHei'  # 替换为字体的名称
plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题

class Box:
    def __init__(self, length, width, height):
        self.length = length
        self.width = width
        self.height = height
        self.volume = length * width * height
        
    def get_rotations(self):
        """获取所有可能的摆放方向"""
        return [
            (self.length, self.width, self.height),
            (self.width, self.length, self.height),
            (self.length, self.height, self.width),
            (self.height, self.length, self.width),
            (self.width, self.height, self.length),
            (self.height, self.width, self.length)
        ]

class Pallet:
    def __init__(self, length, width, max_height):
        self.length = length
        self.width = width
        self.max_height = max_height
        self.volume = length * width * max_height

def place_box(x, y, l, w, layer_info, pallet, support_map, current_support, layer_count, total_boxes, box_type):
    """尝试放置箱子，并更新支撑区域"""
    # 检查是否超出托盘边界
    if x + l > pallet.length or y + w > pallet.width:
        return False
    
    # 检查支撑条件（从第二层开始）
    if layer_count > 0:
        # 检查四个关键点（减少计算量）
        corners = [
            (int(x), int(y)),
            (int(x+l-1), int(y)),
            (int(x), int(y+w-1)),
            (int(x+l-1), int(y+w-1))
        ]
        if not all(current_support[c[0], c[1]] for c in corners):
            return False
    
    # 检查是否与其他箱子重叠
    for box in layer_info["box_positions"]:
        if (x < box["x"] + box["l"] and 
            x + l > box["x"] and 
            y < box["y"] + box["w"] and 
            y + w > box["y"]):
            return False
    
    # 通过所有检查，放置箱子
    layer_info["box_positions"].append({
        "type": box_type,
        "x": x,
        "y": y,
        "l": l,
        "w": w
    })
    total_boxes += 1
    
    # 更新当前层支撑地图
    x_end = min(int(x + l), pallet.length)
    y_end = min(int(y + w), pallet.width)
    support_map[int(x):x_end, int(y):y_end] = True
    
    return True

def calculate_alternating_layout(box, pallet, orientation):
    """改进的纵横式堆码算法，支持剩余空间旋转放置"""
    l, w, h = orientation
    if h > pallet.max_height:
        return None
    
    total_boxes = 0
    current_z = 0
    layer_count = 0
    layout_details = []
    total_volume = 0
    
    # 初始化支撑地图（第一层托盘底部全支撑）
    support_map = np.ones((int(pallet.length)+1, int(pallet.width)+1), dtype=bool) if layer_count == 0 else np.zeros((int(pallet.length)+1, int(pallet.width)+1), dtype=bool)
    
    while current_z + h <= pallet.max_height:
        # 当前层的实际支撑条件
        current_support = support_map.copy()
        # 重置当前层的支撑地图
        support_map = np.zeros((int(pallet.length)+1, int(pallet.width)+1), dtype=bool)
        
        # 创建当前层信息
        layer_info = {
            "layer": layer_count + 1,
            "orientation": (l, w, h),
            "box_positions": []
        }
        
        # 确定当前层的方向（交替变化）
        if layer_count % 2 == 0:
            layer_length = l
            layer_width = w
        else:
            layer_length = w
            layer_width = l
        
        # 计算主方向排列
        x_num = int(pallet.length // layer_length)
        y_num = int(pallet.width // layer_width)
        
        # 放置主排列箱子
        for x in range(x_num):
            for y in range(y_num):
                x_pos = x * layer_length
                y_pos = y * layer_width
                if place_box(x_pos, y_pos, layer_length, layer_width, layer_info, pallet, 
                                support_map, current_support, layer_count, total_boxes, "main"):
                    total_boxes += 1
        
        # 计算剩余空间
        x_remain = pallet.length - x_num * layer_length
        y_remain = pallet.width - y_num * layer_width
        
        # 横向剩余空间利用（右侧区域）
        if x_remain > 0 and y_num > 0:
            x_start = x_num * layer_length
            
            # 尝试正常方向
            if x_remain >= layer_width:
                for y in range(y_num):
                    y_pos = y * layer_width
                    place_box(x_start, y_pos, layer_width, layer_width, layer_info, pallet, 
                                support_map, current_support, layer_count, total_boxes, "extra_x")
            
            # 尝试旋转方向
            for rotation in [(w, l), (l, w)]:
                rot_l, rot_w = rotation
                if rot_l <= x_remain and (rot_w <= layer_width or layer_count == 0):
                    for y in range(y_num):
                        y_pos = y * layer_width
                        place_box(x_start, y_pos, rot_l, rot_w, layer_info, pallet, 
                                    support_map, current_support, layer_count, total_boxes, "extra_x_rot")
        
        # 纵向剩余空间利用（上方区域）
        if y_remain > 0 and x_num > 0:
            y_start = y_num * layer_width
            
            # 尝试正常方向
            if y_remain >= layer_length:
                for x in range(x_num):
                    x_pos = x * layer_length
                    place_box(x_pos, y_start, layer_length, layer_length, layer_info, pallet, 
                                support_map, current_support, layer_count, total_boxes, "extra_y")
            
            # 尝试旋转方向
            for rotation in [(w, l), (l, w)]:
                rot_l, rot_w = rotation
                if rot_w <= y_remain and (rot_l <= layer_length or layer_count == 0):
                    for x in range(x_num):
                        x_pos = x * layer_length
                        place_box(x_pos, y_start, rot_l, rot_w, layer_info, pallet, 
                                    support_map, current_support, layer_count, total_boxes, "extra_y_rot")
        
        # 计算当前层体积
        if layer_info["box_positions"]:
            layer_volume = sum(box["l"] * box["w"] * h for box in layer_info["box_positions"])
            total_volume += layer_volume
            layout_details.append(layer_info)
            current_z += h
            layer_count += 1
        else:
            break  # 无法放置更多层时终止

    if total_boxes == 0:
        return None
    
    # 计算空间利用率
    pallet_volume = pallet.length * pallet.width * pallet.max_height
    utilization = total_volume / pallet_volume
    
    return {
        "type": "改进纵横式堆码",
        "orientation": orientation,
        "total_boxes": total_boxes,
        "layers": layer_count,
        "utilization": min(utilization, 1.0),
        "layer_details": layout_details,
        "total_volume": total_volume,
        "pallet_volume": pallet_volume
    }

def plot_2d_layout(pallet, layer_info):
    """生成2D层布局图"""
    fig, ax = plt.subplots(figsize=(8, 6))
    
    # 绘制托盘边界
    ax.add_patch(plt.Rectangle((0, 0), pallet.length, pallet.width, 
                                fill=False, edgecolor='black', linewidth=2))
    
    # 颜色配置
    color_map = {
        "main": "#4ECDC4",     # 青绿色 - 主排列
        "extra_x": "#FFD166",  # 黄色 - 横向剩余
        "extra_x_rot": "#A7C957",  # 浅绿 - 横向旋转
        "extra_y": "#FF9A76",   # 橙色 - 纵向剩余
        "extra_y_rot": "#BDD5EA"   # 浅蓝 - 纵向旋转
    }
    
    # 绘制每个箱子并添加标注
    for box in layer_info["box_positions"]:
        box_type = box["type"] if box["type"] in color_map else "main"
        ax.add_patch(plt.Rectangle(
            (box["x"], box["y"]), 
            box["l"], 
            box["w"],
            facecolor=color_map[box_type],
            edgecolor='black',
            alpha=0.8
        ))
        
        # 添加尺寸标注
        label = f"{box['l']}×{box['w']}"
        ax.text(box["x"] + box["l"]/2, box["y"] + box["w"]/2, 
                label, ha='center', va='center', fontsize=8, color='black')
        
        # 如果是旋转放置，添加旋转标记
        if "_rot" in box["type"]:
            ax.text(box["x"] + box["l"]/2, box["y"] + box["w"]/2, 
                    "旋转", ha='center', va='center', fontsize=10, color='red', weight='bold', alpha=0.9)
    
    # 添加比例箭头
    arrow_length = min(pallet.length, pallet.width) * 0.2
    ax.arrow(5, 5, arrow_length, 0, head_width=3, head_length=5, fc='k', ec='k')
    ax.arrow(5, 5, 0, arrow_length, head_width=3, head_length=5, fc='k', ec='k')
    ax.text(5 + arrow_length/2, 2, '长度 (cm)', ha='center')
    ax.text(2, 5 + arrow_length/2, '宽度 (cm)', ha='center', rotation='vertical')
    
    # 设置坐标轴范围
    ax.set_xlim(-0.05 * pallet.length, pallet.length * 1.05)
    ax.set_ylim(-0.05 * pallet.width, pallet.width * 1.05)
    
    # 计算利用率
    used_area = sum(box["l"] * box["w"] for box in layer_info["box_positions"])
    layer_utilization = used_area / (pallet.length * pallet.width)
    
    ax.set_title(f"第{layer_info['layer']}层 - 箱数: {len(layer_info['box_positions'])} - 利用率: {layer_utilization*100:.1f}%", 
                fontsize=12)
    ax.set_aspect('equal')
    ax.grid(True, linestyle='--', alpha=0.3)
    
    # 添加图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_map['main'], label='主排列'),
        Patch(facecolor=color_map['extra_x'], label='横向补充'),
        Patch(facecolor=color_map['extra_x_rot'], label='横向旋转'),
        Patch(facecolor=color_map['extra_y'], label='纵向补充'),
        Patch(facecolor=color_map['extra_y_rot'], label='纵向旋转')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    return fig

def plot_3d_layout(pallet, layout):
    """生成3D可视化图形"""
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # 绘制托盘
    tray = Poly3DCollection([
        [(0, 0, 0), (pallet.length, 0, 0), (pallet.length, pallet.width, 0), (0, pallet.width, 0)]
    ])
    tray.set_facecolor('#CCCCCC')
    tray.set_alpha(0.5)
    tray.set_edgecolor('k')
    ax.add_collection3d(tray)
    
    # 颜色配置
    color_map = {
        "main": "#4ECDC4",     # 青绿色
        "extra_x": "#4ECDC4",  # 青绿色
        "extra_x_rot": "#A7C957",  # 浅绿
        "extra_y": "#4ECDC4",   # 青绿色
        "extra_y_rot": "#BDD5EA"   # 浅蓝
    }
    
    # 绘制每个箱子
    for layer_info in layout["layer_details"]:
        layer_z = (layer_info["layer"] - 1) * layout["orientation"][2]
        
        for box in layer_info["box_positions"]:
            # 绘制六面体
            x, y = box["x"], box["y"]
            l, w = box["l"], box["w"]
            h = layout["orientation"][2]
            
            # 定义六面体的8个顶点
            v = np.array([
                [x, y, layer_z], [x+l, y, layer_z], [x+l, y+w, layer_z], [x, y+w, layer_z],
                [x, y, layer_z+h], [x+l, y, layer_z+h], [x+l, y+w, layer_z+h], [x, y+w, layer_z+h]
            ])
            
            # 定义六面体的6个面
            faces = [
                [v[0], v[1], v[5], v[4]],  # 前面
                [v[1], v[2], v[6], v[5]],  # 右面
                [v[2], v[3], v[7], v[6]],  # 后面
                [v[3], v[0], v[4], v[7]],  # 左面
                [v[4], v[5], v[6], v[7]],  # 顶面
                [v[0], v[1], v[2], v[3]]   # 底面
            ]
            
            # 选择箱子颜色
            box_color = color_map.get(box["type"], "#4ECDC4")
            cube = Poly3DCollection(faces, facecolors=box_color, 
                                    edgecolor='k', alpha=0.85, linewidths=0.8)
            ax.add_collection3d(cube)
    
    # 坐标轴设置
    ax.set_xlim(0, pallet.length * 1.1)
    ax.set_ylim(0, pallet.width * 1.1)
    max_z = min(pallet.max_height, max([(layer_info["layer"] * layout["orientation"][2]) 
                                        for layer_info in layout["layer_details"]], default=0))
    ax.set_zlim(0, max_z * 1.1)
    
    ax.set_xlabel('托盘长度 (cm)', labelpad=15)
    ax.set_ylabel('托盘宽度 (cm)', labelpad=15)
    ax.set_zlabel('堆码高度 (cm)', labelpad=15)
    
    # 添加标题
    ax.set_title(
        f"总箱数: {layout['total_boxes']} / 堆码层数: {layout['layers']}",
        pad=20
    )
    
    # 设置视角
    ax.view_init(elev=35, azim=-50)
    ax.set_box_aspect([pallet.length, pallet.width, max_z])
    
    plt.tight_layout()
    return fig

def visualize_optimization(box, pallet, original, optimized):
    """显示优化前后对比"""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # 原方案
    ax1.barh(['总箱数', '利用率(%)', '层数'], 
                [original['total_boxes'], original['utilization']*100, original['layers']],
                color=['#4ECDC4', '#FF9A76', '#FFD166'])
    ax1.set_title('原方案结果')
    ax1.set_xlim(0, max(100, original['total_boxes']*1.3, original['utilization']*100 * 1.3))
    ax1.grid(axis='x', linestyle='--', alpha=0.3)
    ax1.set_xlabel('数值')
    
    # 优化方案
    ax2.barh(['总箱数', '利用率(%)', '层数'], 
                [optimized['total_boxes'], optimized['utilization']*100, optimized['layers']],
                color=['#4ECDC4', '#FF9A76', '#FFD166'])
    ax2.set_title('优化后方案')
    ax2.set_xlim(0, max(100, optimized['total_boxes']*1.3, optimized['utilization']*100 * 1.3))
    ax2.grid(axis='x', linestyle='--', alpha=0.3)
    ax2.set_xlabel('数值')
    
    # 添加数值标签
    for ax, data in zip([ax1, ax2], [original, optimized]):
        for i, (k, v) in enumerate(data.items()):
            if k not in ['total_boxes', 'utilization', 'layers']:
                continue
            if k == 'utilization':
                ax.text(v*100, i, f"{v*100:.1f}%", ha='left', va='center', fontsize=12)
            else:
                ax.text(v, i, str(v), ha='left', va='center', fontsize=12)
    
    fig.suptitle(f"优化效果对比 (箱子尺寸: {box.length}×{box.width}×{box.height}cm | 托盘: {pallet.length}×{pallet.width}×{pallet.max_height}cm)", 
                    fontsize=14)
    plt.tight_layout()
    return fig

def calculate_alternating_layout_original(box, pallet, orientation):
    """原始纵横式堆码算法（用于对比）"""
    l, w, h = orientation
    if h > pallet.max_height:
        return None
    
    total_boxes = 0
    current_z = 0
    layer_count = 0
    layout_details = []
    total_volume = 0
    
    while current_z + h <= pallet.max_height:
        # 确定当前层的方向（交替变化）
        if layer_count % 2 == 0:
            layer_length = l
            layer_width = w
        else:
            layer_length = w
            layer_width = l

        layer_info = {
            "layer": layer_count + 1,
            "orientation": (layer_length, layer_width, h),
            "box_positions": []
        }

        # 计算主方向排列
        x_num = int(pallet.length // layer_length)
        y_num = int(pallet.width // layer_width)
        
        # 放置主排列箱子
        for x in range(x_num):
            for y in range(y_num):
                x_pos = x * layer_length
                y_pos = y * layer_width
                
                layer_info["box_positions"].append({
                    "type": "main",
                    "x": x_pos,
                    "y": y_pos,
                    "l": layer_length,
                    "w": layer_width
                })
                total_boxes += 1

        # 计算当前层体积
        if layer_info["box_positions"]:
            layer_volume = len(layer_info["box_positions"]) * layer_length * layer_width * h
            total_volume += layer_volume
            layout_details.append(layer_info)
            current_z += h
            layer_count += 1
        else:
            break

    if total_boxes == 0:
        return None
    
    # 计算空间利用率
    pallet_volume = pallet.length * pallet.width * pallet.max_height
    utilization = total_volume / pallet_volume
    
    return {
        "type": "原始纵横式堆码",
        "orientation": orientation,
        "total_boxes": total_boxes,
        "layers": layer_count,
        "utilization": min(utilization, 1.0),
        "layer_details": layout_details,
        "total_volume": total_volume,
        "pallet_volume": pallet_volume
    }

def get_fig_download_link(fig):
    """生成3D视图下载链接"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()
    return f'<a href="data:image/png;base64,{b64}" download="stacking_3d_view.png">下载3D视图 (PNG格式)</a>'

def main():
    st.title("📦 纵横式码垛方案可视化")
    
    # 初始化session状态
    if 'run' not in st.session_state:
        st.session_state.run = False
    if 'prev_params' not in st.session_state:
        st.session_state.prev_params = None
    
    # 侧边栏输入
    with st.sidebar:
        st.header("参数设置")
        box_l = st.number_input("箱子长度 (cm)", min_value=1, value=20)
        box_w = st.number_input("箱子宽度 (cm)", min_value=1, value=35)
        box_h = st.number_input("箱子高度 (cm)", min_value=1, value=40)
        
        pallet_l = st.number_input("托盘长度 (cm)", min_value=1, value=120)
        pallet_w = st.number_input("托盘宽度 (cm)", min_value=1, value=100)
        pallet_h = st.number_input("最大堆高 (cm)", min_value=1, value=200)
        
        current_params = (box_l, box_w, box_h, pallet_l, pallet_w, pallet_h)
        
        if st.button("计算堆码方案", type="primary") or (st.session_state.run and current_params != st.session_state.prev_params):
            st.session_state.run = True
            st.session_state.prev_params = current_params

    if st.session_state.run:
        box = Box(box_l, box_w, box_h)
        pallet = Pallet(pallet_l, pallet_w, pallet_h)
        
        # 计算原始方案（用于对比）
        with st.spinner('计算原始方案...'):
            start_time = time.time()
            original_layout = None
            for orient in box.get_rotations():
                result = calculate_alternating_layout_original(box, pallet, orient)
                if result and (original_layout is None or result['total_boxes'] > original_layout['total_boxes']):
                    original_layout = result
            original_time = time.time() - start_time
            
        # 计算改进方案
        with st.spinner('计算优化方案...'):
            start_time = time.time()
            optimized_layout = None
            for orient in box.get_rotations():
                result = calculate_alternating_layout(box, pallet, orient)
                if result and (optimized_layout is None or result['total_boxes'] > optimized_layout['total_boxes']):
                    optimized_layout = result
            optimized_time = time.time() - start_time
        
        if original_layout and optimized_layout:
            # 显示最佳方案
            st.subheader("最优堆码方案")
            cols = st.columns(3)
            cols[0].metric("总箱数", optimized_layout["total_boxes"])
            cols[1].metric("堆码层数", optimized_layout["layers"])
            cols[2].metric("空间利用率", f"{optimized_layout['utilization']*100:.1f}%")
            
            st.markdown(f"""
            **箱子参数**  
            ▪ 长×宽×高: `{box_l}×{box_w}×{box_h}`cm  
            **托盘参数**  
            ▪ 长×宽×最大堆高: `{pallet_l}×{pallet_w}×{pallet_h}`cm  
            **容积利用**  
            ▪ 箱子总体积: `{optimized_layout['total_volume']/1000000:.2f}` m³  
            ▪ 托盘容量: `{optimized_layout['pallet_volume']/1000000:.2f}` m³
            """)

            # 3D可视化
            st.subheader("3D堆码示意图")
            fig_3d = plot_3d_layout(pallet, optimized_layout)
            st.pyplot(fig_3d)

            # 提供3D视图下载
            st.markdown(get_fig_download_link(fig_3d), unsafe_allow_html=True)

            # # 2D分层可视化
            # st.subheader("2D堆码示意图")
            # if len(optimized_layout["layer_details"]) > 0:
            #     tabs = st.tabs([f"第{layer['layer']}层" for layer in optimized_layout["layer_details"]])
            #     for i, tab in enumerate(tabs):
            #         with tab:
            #             layer_fig = plot_2d_layout(pallet, optimized_layout["layer_details"][i])
                        # st.pyplot(layer_fig)
            
        else:
            st.error("未找到可行方案，请调整尺寸参数")

if __name__ == "__main__":
    main()