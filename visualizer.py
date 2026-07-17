# -*- coding: utf-8 -*-
"""
fund_analyzer/core/visualizer.py
基金分析工具 —— 可视化模块

基于 pyecharts 生成交互式 HTML 图表，包括：
- 净值走势图
- 收益对比图
- 类型分布饼图
- 相关性热力图
- 日增长率分布图
"""

import os
import numpy as np
import pandas as pd
from typing import Optional

from pyecharts.charts import Line, Bar, Pie, HeatMap
from pyecharts import options as opts
from pyecharts.globals import ThemeType
from pyecharts.commons.utils import JsCode


# ============================================================
# 工具函数
# ============================================================

def _ensure_dir(path: str):
    """确保输出目录存在"""
    dir_path = os.path.dirname(path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)


def _get_common_title_opts(title: str, subtitle: str = "") -> opts.TitleOpts:
    """生成统一的标题配置"""
    return opts.TitleOpts(
        title=title,
        subtitle=subtitle,
        pos_left="center",
        title_textstyle_opts=opts.TextStyleOpts(
            font_size=20,
            font_weight="bold",
            color="#2c3e50"
        ),
        subtitle_textstyle_opts=opts.TextStyleOpts(
            font_size=12,
            color="#7f8c8d"
        )
    )


def _get_common_toolbox_opts() -> opts.ToolboxOpts:
    """生成统一的工具箱配置"""
    return opts.ToolboxOpts(
        is_show=True,
        pos_left="right",
        pos_top="top",
        feature=opts.ToolBoxFeatureOpts(
            save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(
                title="保存图片",
                pixel_ratio=2
            ),
            data_zoom=opts.ToolBoxFeatureDataZoomOpts(
                zoom_title="区域缩放",
                back_title="缩放还原"
            ),
            restore=opts.ToolBoxFeatureRestoreOpts(title="还原"),
            magic_type=opts.ToolBoxFeatureMagicTypeOpts(
                line_title="折线图",
                bar_title="柱状图",
                stack_title="堆叠"
            ),
            data_view=opts.ToolBoxFeatureDataViewOpts(title="数据视图"),
        )
    )


def _get_common_datazoom_opts() -> list:
    """生成统一的数据缩放配置"""
    return [
        opts.DataZoomOpts(
            type_="slider",
            range_start=0,
            range_end=100,
            pos_bottom=10
        ),
        opts.DataZoomOpts(type_="inside", range_start=0, range_end=100),
    ]


def _get_common_tooltip_opts(trigger: str = "axis") -> opts.TooltipOpts:
    """生成统一的提示框配置"""
    return opts.TooltipOpts(
        trigger=trigger,
        axis_pointer_type="cross",
        background_color="rgba(255,255,255,0.95)",
        border_color="#ccc",
        border_width=1,
        textstyle_opts=opts.TextStyleOpts(color="#333"),
        formatter=JsCode(
            """function(params){
                if(Array.isArray(params)){
                    let res = params[0].axisValue + '<br/>';
                    params.forEach(function(item){
                        let marker = item.marker;
                        let val = typeof item.value === 'number' ? item.value.toFixed(4) : item.value;
                        res += marker + ' ' + item.seriesName + ': ' + val + '<br/>';
                    });
                    return res;
                }
                return params.name + ': ' + params.value;
            }"""
        ) if trigger == "axis" else None
    )


def _get_chart_init_opts(width: str = "1200px", height: str = "600px") -> dict:
    """生成统一的图表初始化配置"""
    return {
        "width": width,
        "height": height,
        "theme": ThemeType.LIGHT,
        "bg_color": "#fafbfc"
    }


# ============================================================
# 图表 1: 净值走势图
# ============================================================

def plot_net_value_trend(
    fund_code: str,
    df_history: pd.DataFrame,
    output_path: str
):
    """
    绘制单只基金的净值走势图

    参数:
        fund_code: 基金代码，用于标题显示
        df_history: 历史净值 DataFrame，需包含列 [净值日期, 单位净值, 累计净值]
        output_path: 输出 HTML 文件路径
    """
    _ensure_dir(output_path)

    # 防御性检查
    if df_history is None or df_history.empty:
        print(f"[警告] 基金 {fund_code} 的历史数据为空，无法绘制走势图")
        return

    required_cols = {"净值日期", "单位净值", "累计净值"}
    if not required_cols.issubset(set(df_history.columns)):
        print(f"[警告] 缺少必要列，当前列: {list(df_history.columns)}")
        return

    # 数据排序：按日期升序
    df = df_history.copy()
    df["净值日期"] = pd.to_datetime(df["净值日期"])
    df = df.sort_values("净值日期").reset_index(drop=True)

    # 提取数据
    date_list = df["净值日期"].dt.strftime("%Y-%m-%d").tolist()
    unit_values = df["单位净值"].astype(float).round(4).tolist()
    accum_values = df["累计净值"].astype(float).round(4).tolist()

    # 构建折线图
    line = (
        Line(init_opts=opts.InitOpts(**_get_chart_init_opts("1200px", "650px")))
        .set_global_opts(
            title_opts=_get_common_title_opts(
                title=f"基金 {fund_code} 净值走势",
                subtitle=f"数据区间: {date_list[0]} 至 {date_list[-1]}  共 {len(date_list)} 个交易日"
            ),
            legend_opts=opts.LegendOpts(
                pos_top=40,
                orient="horizontal",
                item_width=30,
                item_height=14,
                textstyle_opts=opts.TextStyleOpts(font_size=13)
            ),
            tooltip_opts=_get_common_tooltip_opts("axis"),
            toolbox_opts=_get_common_toolbox_opts(),
            datazoom_opts=_get_common_datazoom_opts(),
            xaxis_opts=opts.AxisOpts(
                name="日期",
                type_="category",
                axislabel_opts=opts.LabelOpts(rotate=30, font_size=11),
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold")
            ),
            yaxis_opts=opts.AxisOpts(
                name="净值 (元)",
                type_="value",
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold"),
                splitline_opts=opts.SplitLineOpts(is_show=True, linestyle_opts=opts.LineStyleOpts(opacity=0.3)),
                axislabel_opts=opts.LabelOpts(font_size=11)
            ),
        )
        .add_xaxis(date_list)
        .add_yaxis(
            series_name="单位净值",
            y_axis=unit_values,
            is_smooth=True,
            symbol="circle",
            symbol_size=4,
            is_connect_nones=True,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=2.5, color="#5470c6"),
            itemstyle_opts=opts.ItemStyleOpts(color="#5470c6", border_width=1),
            areastyle_opts=opts.AreaStyleOpts(
                opacity=0.15,
                color=JsCode("""new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    {offset: 0, color: 'rgba(84, 112, 198, 0.4)'},
                    {offset: 1, color: 'rgba(84, 112, 198, 0.05)'}
                ])""")
            ),
            markpoint_opts=opts.MarkPointOpts(
                data=[
                    opts.MarkPointItem(type_="max", name="最高"),
                    opts.MarkPointItem(type_="min", name="最低"),
                ],
                label_opts=opts.LabelOpts(font_size=10, color="#fff", background_color="rgba(0,0,0,0.6)")
            ),
            markline_opts=opts.MarkLineOpts(
                data=[opts.MarkLineItem(type_="average", name="均值")],
                linestyle_opts=opts.LineStyleOpts(type_="dashed", opacity=0.6),
                label_opts=opts.LabelOpts(font_size=10)
            ),
        )
        .add_yaxis(
            series_name="累计净值",
            y_axis=accum_values,
            is_smooth=True,
            symbol="diamond",
            symbol_size=4,
            is_connect_nones=True,
            label_opts=opts.LabelOpts(is_show=False),
            linestyle_opts=opts.LineStyleOpts(width=2.5, color="#91cc75"),
            itemstyle_opts=opts.ItemStyleOpts(color="#91cc75", border_width=1),
            areastyle_opts=opts.AreaStyleOpts(
                opacity=0.1,
                color=JsCode("""new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    {offset: 0, color: 'rgba(145, 204, 117, 0.3)'},
                    {offset: 1, color: 'rgba(145, 204, 117, 0.03)'}
                ])""")
            ),
            markpoint_opts=opts.MarkPointOpts(
                data=[
                    opts.MarkPointItem(type_="max", name="最高"),
                    opts.MarkPointItem(type_="min", name="最低"),
                ],
                label_opts=opts.LabelOpts(font_size=10, color="#fff", background_color="rgba(0,0,0,0.6)")
            ),
        )
    )

    line.render(output_path)
    print(f"[图表已生成] 净值走势图 -> {os.path.abspath(output_path)}")


# ============================================================
# 图表 2: 收益对比图
# ============================================================

def plot_return_comparison(
    compare_df: pd.DataFrame,
    output_path: str
):
    """
    绘制多只基金的收益对比柱状图

    参数:
        compare_df: 对比 DataFrame，行=基金，列包含 [总收益率, 年化收益率, 最大回撤]
        output_path: 输出 HTML 文件路径
    """
    _ensure_dir(output_path)

    if compare_df is None or compare_df.empty:
        print("[警告] 对比数据为空，无法生成对比图")
        return

    # 标准化列名（允许中文和英文列名混用）
    col_map = {}
    for c in compare_df.columns:
        col_lower = str(c).lower()
        if any(k in col_lower for k in ["total", "总收益率"]):
            col_map[c] = "总收益率"
        elif any(k in col_lower for k in ["annual", "年化收益率"]):
            col_map[c] = "年化收益率"
        elif any(k in col_lower for k in ["max_drawdown", "最大回撤"]):
            col_map[c] = "最大回撤"
    # 若未匹配到，使用前三列
    if not col_map and len(compare_df.columns) >= 3:
        col_map[compare_df.columns[0]] = "总收益率"
        col_map[compare_df.columns[1]] = "年化收益率"
        col_map[compare_df.columns[2]] = "最大回撤"

    df = compare_df.rename(columns=col_map)

    # 提取基金名称/代码作为 X 轴
    fund_labels = df.index.tolist()
    if "基金名称" in df.columns:
        fund_labels = df["基金名称"].tolist()
    elif "基金简称" in df.columns:
        fund_labels = df["基金简称"].tolist()
    elif "基金代码" in df.columns:
        fund_labels = df["基金代码"].tolist()

    # 提取数值
    total_returns = df.get("总收益率", pd.Series([0] * len(df))).astype(float).round(2).tolist()
    annual_returns = df.get("年化收益率", pd.Series([0] * len(df))).astype(float).round(2).tolist()
    max_drawdowns = df.get("最大回撤", pd.Series([0] * len(df))).astype(float).round(2).tolist()

    # 构建柱状图
    bar = (
        Bar(init_opts=opts.InitOpts(**_get_chart_init_opts("1200px", "650px")))
        .set_global_opts(
            title_opts=_get_common_title_opts(
                title="多只基金收益对比",
                subtitle="总收益率 / 年化收益率 / 最大回撤"
            ),
            legend_opts=opts.LegendOpts(
                pos_top=45,
                orient="horizontal",
                item_width=25,
                item_height=14,
                textstyle_opts=opts.TextStyleOpts(font_size=12)
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="shadow",
                background_color="rgba(255,255,255,0.95)",
                border_color="#ccc",
                border_width=1,
                formatter=JsCode(
                    """function(params){
                        let res = params[0].axisValue + '<br/>';
                        params.forEach(function(item){
                            let marker = item.marker;
                            let val = item.value !== undefined ? item.value.toFixed(2) + '%' : '-';
                            res += marker + ' ' + item.seriesName + ': ' + val + '<br/>';
                        });
                        return res;
                    }"""
                )
            ),
            toolbox_opts=_get_common_toolbox_opts(),
            xaxis_opts=opts.AxisOpts(
                name="基金",
                type_="category",
                axislabel_opts=opts.LabelOpts(rotate=35, font_size=11),
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold")
            ),
            yaxis_opts=opts.AxisOpts(
                name="收益率 / 回撤 ( % )",
                type_="value",
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold"),
                axislabel_opts=opts.LabelOpts(font_size=11, formatter="{value}%"),
                splitline_opts=opts.SplitLineOpts(is_show=True, linestyle_opts=opts.LineStyleOpts(opacity=0.3))
            )
        )
        .add_xaxis(fund_labels)
        .add_yaxis(
            series_name="总收益率",
            y_axis=total_returns,
            bar_width="22%",
            itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(
                    """function(params){
                        var v = params.value;
                        return v >= 0 ? '#5470c6' : '#ee6666';
                    }"""
                ),
                border_radius=[4, 4, 0, 0]
            ),
            label_opts=opts.LabelOpts(
                is_show=True,
                position="top",
                font_size=10,
                formatter=JsCode(
                    "function(p){return p.value >= 0 ? p.value.toFixed(1)+'%' : ''; }"
                )
            )
        )
        .add_yaxis(
            series_name="年化收益率",
            y_axis=annual_returns,
            bar_width="22%",
            itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(
                    """function(params){
                        var v = params.value;
                        return v >= 0 ? '#91cc75' : '#fac858';
                    }"""
                ),
                border_radius=[4, 4, 0, 0]
            ),
            label_opts=opts.LabelOpts(
                is_show=True,
                position="top",
                font_size=10,
                formatter=JsCode(
                    "function(p){return p.value >= 0 ? p.value.toFixed(1)+'%' : ''; }"
                )
            )
        )
        .add_yaxis(
            series_name="最大回撤",
            y_axis=max_drawdowns,
            bar_width="22%",
            itemstyle_opts=opts.ItemStyleOpts(
                color="#ee6666",
                border_radius=[4, 4, 0, 0]
            ),
            label_opts=opts.LabelOpts(
                is_show=True,
                position="bottom",
                font_size=10,
                formatter=JsCode(
                    "function(p){return p.value < 0 ? p.value.toFixed(1)+'%' : ''; }"
                ),
                color="#ee6666"
            )
        )
    )

    bar.render(output_path)
    print(f"[图表已生成] 收益对比图 -> {os.path.abspath(output_path)}")


# ============================================================
# 图表 3: 基金类型分布饼图
# ============================================================

def plot_type_distribution(
    dist_df: pd.DataFrame,
    output_path: str
):
    """
    绘制基金类型分布环形饼图

    参数:
        dist_df: 分布 DataFrame，需包含 [基金类型, 数量] 列
        output_path: 输出 HTML 文件路径
    """
    _ensure_dir(output_path)

    if dist_df is None or dist_df.empty:
        print("[警告] 分布数据为空，无法生成饼图")
        return

    # 标准化列名
    col_map = {}
    for c in dist_df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ["type", "类型"]):
            col_map[c] = "基金类型"
        elif any(k in cl for k in ["count", "数量", "count", "num"]):
            col_map[c] = "数量"
        elif any(k in cl for k in ["avg", "平均"]):
            col_map[c] = "平均收益"
    df = dist_df.rename(columns=col_map)

    # 提取数据
    if "基金类型" in df.columns:
        types = df["基金类型"].tolist()
        counts = df.get("数量", pd.Series([0] * len(df))).astype(int).tolist()
    else:
        types = df.index.astype(str).tolist()
        counts = df.iloc[:, 0].astype(int).tolist()

    # 构造饼图数据
    total = sum(abs(c) for c in counts)
    pie_data = [
        {"value": abs(c), "name": t}
        for t, c in zip(types, counts)
    ]

    # 配色方案
    color_palette = [
        "#5470c6", "#91cc75", "#fac858", "#ee6666",
        "#73c0de", "#3ba272", "#fc8452", "#9a60b4",
        "#ea7ccc", "#37a2da", "#32c5e9", "#67e0e3"
    ]

    # 构建环形饼图
    pie = (
        Pie(init_opts=opts.InitOpts(**_get_chart_init_opts("900px", "700px")))
        .set_global_opts(
            title_opts=_get_common_title_opts(
                title="基金类型分布",
                subtitle=f"共计 {total} 只基金"
            ),
            legend_opts=opts.LegendOpts(
                type_="scroll",
                pos_left="5%",
                pos_bottom="5%",
                orient="vertical",
                item_width=18,
                item_height=12,
                textstyle_opts=opts.TextStyleOpts(font_size=12)
            ),
            tooltip_opts=opts.TooltipOpts(
                trigger="item",
                background_color="rgba(255,255,255,0.95)",
                border_color="#ccc",
                border_width=1,
                formatter=JsCode(
                    """function(params){
                        var marker = params.marker;
                        var name = params.name;
                        var val = params.value;
                        var pct = params.percent;
                        return marker + ' <b>' + name + '</b><br/>'
                            + '数量: ' + val + ' 只<br/>'
                            + '占比: ' + pct.toFixed(1) + '%';
                    }"""
                )
            ),
            toolbox_opts=_get_common_toolbox_opts()
        )
        .add(
            series_name="基金数量",
            data_pair=pie_data,
            radius=["40%", "70%"],
            center=["55%", "50%"],
            rosetype="radius",
            itemstyle_opts=opts.ItemStyleOpts(
                border_width=2,
                border_color="#fff"
            ),
            label_opts=opts.LabelOpts(
                is_show=True,
                font_size=12,
                formatter=JsCode(
                    """function(params){
                        if(params.percent > 5){
                            return params.name + '\\n' + params.percent.toFixed(1) + '%';
                        }
                        return '';
                    }"""
                ),
                color="#333"
            ),
            emphasis_opts=opts.EmphasisOpts(
                label_opts=opts.LabelOpts(
                    font_size=16,
                    font_weight="bold"
                )
            ),
        )
        .set_colors(color_palette)
    )

    pie.render(output_path)
    print(f"[图表已生成] 类型分布饼图 -> {os.path.abspath(output_path)}")


# ============================================================
# 图表 4: 相关性热力图
# ============================================================

def plot_correlation_heatmap(
    corr_df: pd.DataFrame,
    output_path: str
):
    """
    绘制基金相关性热力图

    参数:
        corr_df: 相关性矩阵 DataFrame，index/columns 均为基金代码/名称
        output_path: 输出 HTML 文件路径
    """
    _ensure_dir(output_path)

    if corr_df is None or corr_df.empty:
        print("[警告] 相关性数据为空，无法生成热力图")
        return

    # 确保矩阵是方阵
    fund_names = corr_df.index.astype(str).tolist()
    n = len(fund_names)

    # 构造热力图数据: [x, y, value]
    heat_data = []
    for i in range(n):
        for j in range(n):
            val = float(corr_df.iloc[i, j])
            heat_data.append([i, j, round(val, 3)])

    # 构建热力图
    heatmap = (
        HeatMap(init_opts=opts.InitOpts(**_get_chart_init_opts("850px", "750px")))
        .set_global_opts(
            title_opts=_get_common_title_opts(
                title="基金净值相关性热力图",
                subtitle="数值范围 -1 (负相关) ~ +1 (正相关)"
            ),
            legend_opts=opts.LegendOpts(is_show=False),
            tooltip_opts=opts.TooltipOpts(
                trigger="item",
                background_color="rgba(255,255,255,0.95)",
                border_color="#ccc",
                border_width=1,
                formatter=JsCode(
                    """function(params){
                        var names = """ + str(fund_names) + """;
                        var x = names[params.value[0]];
                        var y = names[params.value[1]];
                        var v = params.value[2];
                        return '<b>' + x + '</b> vs <b>' + y + '</b><br/>'
                            + '相关系数: ' + v.toFixed(3);
                    }"""
                )
            ),
            toolbox_opts=_get_common_toolbox_opts(),
            xaxis_opts=opts.AxisOpts(
                type_="category",
                position="top",
                axislabel_opts=opts.LabelOpts(
                    rotate=45,
                    font_size=11,
                    color="#333"
                ),
                splitarea_opts=opts.SplitAreaOpts(is_show=True)
            ),
            yaxis_opts=opts.AxisOpts(
                type_="category",
                axislabel_opts=opts.LabelOpts(
                    font_size=11,
                    color="#333"
                ),
                splitarea_opts=opts.SplitAreaOpts(is_show=True)
            ),
            visualmap_opts=opts.VisualMapOpts(
                min_=-1,
                max_=1,
                range_color=[
                    "#d94e5d",  # 深红 (-1)
                    "#eac736",  # 黄 (0)
                    "#50a3ba",  # 蓝绿 (1)
                ],
                is_show=True,
                pos_left="5%",
                pos_bottom="5%",
                orient="vertical",
                split_number=10,
                is_calculable=True,
                textstyle_opts=opts.TextStyleOpts(font_size=11)
            )
        )
        .add_xaxis(fund_names)
        .add_yaxis(
            series_name="相关系数",
            yaxis_data=fund_names,
            value=heat_data,
            label_opts=opts.LabelOpts(
                is_show=True,
                font_size=11,
                color="#333",
                formatter=JsCode(
                    """function(params){
                        var v = params.value[2];
                        return v.toFixed(2);
                    }"""
                )
            )
        )
    )

    heatmap.render(output_path)
    print(f"[图表已生成] 相关性热力图 -> {os.path.abspath(output_path)}")


# ============================================================
# 图表 5: 日增长率分布图
# ============================================================

def plot_growth_distribution(
    df: pd.DataFrame,
    output_path: str,
    bins: int = 30
):
    """
    绘制日增长率分布柱状图（分桶直方图）

    参数:
        df: 包含日增长率的数据框，需有 '日增长率' 列
        output_path: 输出 HTML 文件路径
        bins: 分桶数量，默认 30
    """
    _ensure_dir(output_path)

    if df is None or df.empty:
        print("[警告] 数据为空，无法生成分布图")
        return

    # 提取日增长率列
    growth_col = None
    for c in df.columns:
        if "增长" in str(c) or "growth" in str(c).lower():
            growth_col = c
            break

    if growth_col is None:
        # 尝试使用数字类型的列
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                growth_col = c
                break

    if growth_col is None:
        print("[警告] 未找到数值列用于分布图")
        return

    # 清洗数据
    growth = pd.to_numeric(df[growth_col], errors="coerce").dropna()
    if growth.empty:
        print("[警告] 有效数值为空")
        return

    # 计算统计量
    mean_val = growth.mean()
    std_val = growth.std()

    # 分桶
    min_val, max_val = growth.min(), growth.max()
    # 确保范围对称
    limit = max(abs(min_val), abs(max_val))
    # 如果数据非常集中，适当扩展边界
    if limit < 0.1:
        limit = 0.5

    bin_edges = np.linspace(-limit, limit, bins + 1)
    counts, edges = np.histogram(growth, bins=bin_edges)

    # 构造标签 (格式化范围)
    bar_labels = []
    for i in range(len(counts)):
        left = edges[i]
        right = edges[i + 1]
        if abs(left) < 0.01 and abs(right) < 0.01:
            bar_labels.append(f"{left:.3f}~{right:.3f}")
        elif abs(left) < 1 and abs(right) < 1:
            bar_labels.append(f"{left:.2f}~{right:.2f}")
        else:
            bar_labels.append(f"{left:.1f}~{right:.1f}")

    # 根据是否包含均值选择颜色
    colors = []
    for i in range(len(counts)):
        left, right = edges[i], edges[i + 1]
        # 包含均值的高亮
        if left <= mean_val <= right:
            colors.append("#ee6666")  # 红色高亮均值区间
        elif counts[i] > np.mean(counts):
            colors.append("#5470c6")  # 深蓝
        elif counts[i] > 0:
            colors.append("#73c0de")  # 浅蓝
        else:
            colors.append("#d3d3d3")  # 灰色

    # 构建柱状图
    bar = (
        Bar(init_opts=opts.InitOpts(**_get_chart_init_opts("1150px", "600px")))
        .set_global_opts(
            title_opts=_get_common_title_opts(
                title="日增长率分布",
                subtitle=f"均值: {mean_val:.3f} | 标准差: {std_val:.3f} | 样本数: {len(growth)}"
            ),
            legend_opts=opts.LegendOpts(is_show=False),
            tooltip_opts=opts.TooltipOpts(
                trigger="axis",
                axis_pointer_type="shadow",
                background_color="rgba(255,255,255,0.95)",
                border_color="#ccc",
                border_width=1,
                formatter=JsCode(
                    """function(params){
                        var item = params[0];
                        return '区间: ' + item.axisValue + '<br/>'
                            + '频数: ' + item.value + ' 个交易日';
                    }"""
                )
            ),
            toolbox_opts=_get_common_toolbox_opts(),
            datazoom_opts=[
                opts.DataZoomOpts(
                    type_="slider",
                    range_start=0,
                    range_end=100,
                    pos_bottom=10
                )
            ],
            xaxis_opts=opts.AxisOpts(
                name="日增长率区间",
                type_="category",
                axislabel_opts=opts.LabelOpts(rotate=40, font_size=10),
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold")
            ),
            yaxis_opts=opts.AxisOpts(
                name="交易日数量",
                type_="value",
                name_textstyle_opts=opts.TextStyleOpts(font_size=13, font_weight="bold"),
                splitline_opts=opts.SplitLineOpts(is_show=True, linestyle_opts=opts.LineStyleOpts(opacity=0.3)),
                axislabel_opts=opts.LabelOpts(font_size=11)
            )
        )
        .add_xaxis(bar_labels)
        .add_yaxis(
            series_name="频数",
            y_axis=counts.tolist(),
            bar_width="85%",
            itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(
                    """function(params){
                        var colors = """ + str(colors) + """;
                        return colors[params.dataIndex] || '#5470c6';
                    }"""
                ),
                border_radius=[3, 3, 0, 0],
                border_width=0.5,
                border_color="#fff"
            ),
            label_opts=opts.LabelOpts(
                is_show=True,
                position="top",
                font_size=9,
                color="#666",
                formatter=JsCode(
                    "function(p){return p.value > 0 ? p.value : ''; }"
                )
            )
        )
    )

    bar.render(output_path)
    print(f"[图表已生成] 增长率分布图 -> {os.path.abspath(output_path)}")


# ============================================================
# 主函数入口（供命令行快速测试）
# ============================================================

if __name__ == "__main__":
    # 快速测试示例
    print("=" * 60)
    print("基金可视化模块 - 快速测试")
    print("=" * 60)

    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="fund_test_")

    # 测试 1: 净值走势图
    print("\n[测试1] 净值走势图...")
    test_dates = pd.date_range("2024-01-01", periods=60, freq="B")
    np.random.seed(42)
    base = 1.0
    unit_vals = [base]
    for i in range(1, 60):
        base *= (1 + np.random.normal(0.001, 0.008))
        unit_vals.append(round(base, 4))
    accum_vals = [v * (1 + i * 0.0005) for i, v in enumerate(unit_vals)]
    accum_vals = [round(v, 4) for v in accum_vals]

    df_test = pd.DataFrame({
        "净值日期": test_dates.strftime("%Y-%m-%d"),
        "单位净值": unit_vals,
        "累计净值": accum_vals
    })
    plot_net_value_trend("000001", df_test, os.path.join(tmpdir, "net_value_trend.html"))

    # 测试 2: 收益对比图
    print("\n[测试2] 收益对比图...")
    compare_data = pd.DataFrame({
        "总收益率": [15.2, -5.3, 22.1, 8.7, 3.4],
        "年化收益率": [7.1, -2.8, 10.5, 4.2, 1.6],
        "最大回撤": [-8.5, -15.2, -12.3, -6.1, -3.5]
    }, index=[f"基金{chr(65+i)}" for i in range(5)])
    plot_return_comparison(compare_data, os.path.join(tmpdir, "return_comparison.html"))

    # 测试 3: 类型分布饼图
    print("\n[测试3] 类型分布饼图...")
    dist_data = pd.DataFrame({
        "基金类型": ["股票型", "债券型", "混合型", "指数型", "QDII", "货币型"],
        "数量": [120, 85, 150, 60, 25, 200]
    })
    plot_type_distribution(dist_data, os.path.join(tmpdir, "type_distribution.html"))

    # 测试 4: 相关性热力图
    print("\n[测试4] 相关性热力图...")
    np.random.seed(0)
    corr_matrix = np.random.uniform(-1, 1, (5, 5))
    corr_matrix = (corr_matrix + corr_matrix.T) / 2  # 对称化
    np.fill_diagonal(corr_matrix, 1.0)
    corr_df = pd.DataFrame(
        corr_matrix,
        index=[f"基金{i+1}" for i in range(5)],
        columns=[f"基金{i+1}" for i in range(5)]
    )
    plot_correlation_heatmap(corr_df, os.path.join(tmpdir, "correlation_heatmap.html"))

    # 测试 5: 增长率分布图
    print("\n[测试5] 增长率分布图...")
    growth_df = pd.DataFrame({
        "日增长率": np.random.normal(0.001, 0.012, 500)
    })
    plot_growth_distribution(growth_df, os.path.join(tmpdir, "growth_distribution.html"))

    print(f"\n所有测试图表已生成到: {tmpdir}")
