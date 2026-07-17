#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fund_analyzer/main.py
基金分析工具 —— CLI 主程序

基于 colorama 的彩色终端交互界面，整合爬虫、分析、可视化、报告四大模块。
提供基金列表爬取、排行查看、筛选、单基金分析、多基金对比、相关性分析、
可视化图表生成、Excel 导出、一键综合分析等功能。

用法:
    python main.py              # 启动交互式菜单
    python main.py --auto       # 自动运行一键综合分析
"""

import os
import sys
import time
import argparse
from datetime import datetime

from colorama import init, Fore, Style, Back

# ============================================================
# colorama 初始化（Windows 自动重置颜色）
# ============================================================
init(autoreset=True)

# ============================================================
# 路径与目录配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# ============================================================
# 全局状态（当前会话数据缓存）
# ============================================================
_session = {
    "fund_list": None,      # 基金列表 DataFrame
    "ranking": None,        # 排行 DataFrame
    "filtered": None,       # 筛选结果 DataFrame
    "history": {},          # 单只基金历史净值 {fund_code: df}
    "compare": None,        # 对比结果 DataFrame
    "correlation": None,    # 相关性矩阵 DataFrame
}


# ============================================================
# 终端输出工具函数
# ============================================================

def _clear_screen():
    """清屏"""
    os.system("cls" if sys.platform == "win32" else "clear")


def _print_banner():
    """打印主菜单横幅"""
    banner = (
        f"{Fore.CYAN}{'=' * 45}\n"
        f"{Fore.YELLOW}{Style.BRIGHT}         基金分析工具 v1.0\n"
        f"{Fore.CYAN}{'=' * 45}\n"
        f"{Fore.WHITE}  从天天基金网爬取数据 · 筛选 · 分析 · 可视化\n"
        f"{Fore.CYAN}{'=' * 45}"
    )
    print(banner)


def _print_menu():
    """打印主菜单选项"""
    menu = f"""
{Fore.GREEN}请选择操作:

  {Fore.CYAN}1.{Fore.WHITE}  爬取基金列表
  {Fore.CYAN}2.{Fore.WHITE}  查看基金排行 TOP100
  {Fore.CYAN}3.{Fore.WHITE}  筛选优质基金
  {Fore.CYAN}4.{Fore.WHITE}  分析单只基金历史净值
  {Fore.CYAN}5.{Fore.WHITE}  对比多只基金
  {Fore.CYAN}6.{Fore.WHITE}  基金相关性分析
  {Fore.CYAN}7.{Fore.WHITE}  生成可视化图表
  {Fore.CYAN}8.{Fore.WHITE}  导出 Excel 报告
  {Fore.CYAN}9.{Fore.WHITE}  一键综合分析
  {Fore.RED}0.{Fore.WHITE}  退出

{Fore.CYAN}{'=' * 45}"""
    print(menu)


def _print_success(msg: str):
    """打印成功消息"""
    print(f"{Fore.GREEN}[成功] {msg}{Style.RESET_ALL}")


def _print_info(msg: str):
    """打印信息消息"""
    print(f"{Fore.CYAN}[信息] {msg}{Style.RESET_ALL}")


def _print_warning(msg: str):
    """打印警告消息"""
    print(f"{Fore.YELLOW}[警告] {msg}{Style.RESET_ALL}")


def _print_error(msg: str):
    """打印错误消息"""
    print(f"{Fore.RED}[错误] {msg}{Style.RESET_ALL}")


def _input_prompt(prompt: str) -> str:
    """彩色输入提示"""
    return input(f"{Fore.MAGENTA}{prompt}{Fore.WHITE}> {Style.RESET_ALL}")


def _input_confirm(prompt: str) -> bool:
    """确认输入 (y/n)"""
    ans = input(f"{Fore.MAGENTA}{prompt} (y/n){Fore.WHITE}> {Style.RESET_ALL}").strip().lower()
    return ans in ("y", "yes", "是", "1")


def _wait_continue():
    """等待用户按回车继续"""
    input(f"\n{Fore.GREEN}按 Enter 键继续...{Style.RESET_ALL}")


def _print_table(df, max_rows: int = 20, title: str = ""):
    """
    美观地打印 DataFrame 表格
    """
    if df is None or df.empty:
        _print_warning("数据为空")
        return

    if title:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}{title}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─' * 60}")

    # 截取前 N 行
    display_df = df.head(max_rows)
    print(display_df.to_string(index=True))

    if len(df) > max_rows:
        print(f"\n{Fore.CYAN}... 共 {len(df)} 行，显示前 {max_rows} 行")


# ============================================================
# 模块导入与依赖检查
# ============================================================

def _import_core_modules():
    """
    尝试导入核心模块，返回是否成功
    如果模块不存在，给出友好提示
    """
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        _print_error("缺少必要依赖: pandas, numpy")
        print(f"{Fore.YELLOW}请先安装依赖: pip install -r requirements.txt")
        sys.exit(1)

    modules = {}
    module_status = {}

    # 尝试导入各个核心模块
    try:
        from core import crawler
        modules["crawler"] = crawler
        module_status["crawler"] = True
    except ImportError as e:
        module_status["crawler"] = False
        modules["crawler"] = None

    try:
        from core import analyzer
        modules["analyzer"] = analyzer
        module_status["analyzer"] = True
    except ImportError as e:
        module_status["analyzer"] = False
        modules["analyzer"] = None

    try:
        from core import visualizer
        modules["visualizer"] = visualizer
        module_status["visualizer"] = True
    except ImportError as e:
        module_status["visualizer"] = False
        modules["visualizer"] = None

    try:
        from core import reporter
        modules["reporter"] = reporter
        module_status["reporter"] = True
    except ImportError as e:
        module_status["reporter"] = False
        modules["reporter"] = None

    # 打印模块加载状态
    print(f"\n{Fore.CYAN}模块加载状态:")
    for name, status in module_status.items():
        status_str = f"{Fore.GREEN}已加载" if status else f"{Fore.YELLOW}未加载(占位)"
        print(f"  {Fore.WHITE}  {name:12s} {status_str}")
    print()

    # 为未加载的模块创建 Mock 对象
    for name, ok in module_status.items():
        if not ok:
            modules[name] = _MockModule(name)

    return modules


class _MockModule:
    """
    模拟模块占位器
    当核心模块尚未实现时，提供带提示的占位函数
    """

    def __init__(self, name: str):
        self._name = name

    def _placeholder(self, *args, **kwargs):
        _print_warning(f"模块 '{self._name}' 尚未实现或导入失败，此功能暂不可用")
        return None

    def __getattr__(self, item):
        return self._placeholder


# ============================================================
# 菜单 1: 爬取基金列表
# ============================================================

def menu_crawl_fund_list(modules: dict):
    """爬取全部基金列表并保存"""
    _print_info("开始爬取基金列表...")
    crawler = modules.get("crawler")

    df = crawler.get_fund_list()

    if df is None or df.empty:
        _print_error("爬取基金列表失败")
        return

    _session["fund_list"] = df

    # 保存到 CSV
    output_path = os.path.join(DATA_DIR, "funds_list.csv")
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    _print_success(f"共爬取 {len(df)} 只基金，已保存到 {output_path}")
    _print_table(df.head(10), title="前 10 只基金")


# ============================================================
# 菜单 2: 查看基金排行
# ============================================================

def menu_view_ranking(modules: dict):
    """查看基金排行 TOP100"""
    _print_info("正在获取基金排行数据...")
    crawler = modules.get("crawler")

    # 交互式选择基金类型
    print(f"\n{Fore.CYAN}基金类型选项: all=全部, gp=股票型, zq=债券型, hh=混合型")
    fund_type = _input_prompt("请输入基金类型 [默认 all]").strip() or "all"

    # 排序选项
    print(f"\n{Fore.CYAN}排序选项: 1nzf=近1月, 3nzf=近3月, 6nzf=近6月, 1y=近1年, 2y=近2年, 3y=近3年")
    sort_by = _input_prompt("请输入排序字段 [默认 1y]").strip() or "1y"

    try:
        top_n = int(_input_prompt("显示前 N 条 [默认 100]").strip() or "100")
    except ValueError:
        top_n = 100

    df = crawler.get_fund_ranking(fund_type=fund_type, sort_by=sort_by, top_n=top_n)

    if df is None or df.empty:
        _print_error("获取排行数据失败")
        return

    _session["ranking"] = df

    # 显示结果
    _print_success(f"共获取 {len(df)} 条排行数据")
    _print_table(df.head(20), title=f"基金排行 TOP20 (类型={fund_type}, 排序={sort_by})")

    # 可选导出
    if _input_confirm("是否导出排行到 CSV"):
        output_path = os.path.join(DATA_DIR, "funds_ranking.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        _print_success(f"已导出到 {output_path}")


# ============================================================
# 菜单 3: 筛选优质基金
# ============================================================

def menu_filter_funds(modules: dict):
    """交互式筛选优质基金"""
    analyzer = modules.get("analyzer")

    # 确保有数据源
    df_source = None
    source_name = ""

    if _session["ranking"] is not None:
        df_source = _session["ranking"]
        source_name = "当前排行数据"
    elif _session["fund_list"] is not None:
        df_source = _session["fund_list"]
        source_name = "基金列表数据"
    else:
        _print_info("暂无数据，先尝试加载本地排行数据...")
        ranking_path = os.path.join(DATA_DIR, "funds_ranking.csv")
        list_path = os.path.join(DATA_DIR, "funds_list.csv")
        if os.path.exists(ranking_path):
            import pandas as pd
            df_source = pd.read_csv(ranking_path)
            source_name = "本地排行文件"
            _session["ranking"] = df_source
        elif os.path.exists(list_path):
            import pandas as pd
            df_source = pd.read_csv(list_path)
            source_name = "本地基金列表"
            _session["fund_list"] = df_source
        else:
            _print_error("没有可用数据，请先执行菜单 1 或 2 获取数据")
            return

    _print_info(f"使用数据源: {source_name} ({len(df_source)} 条)")

    # 交互式输入筛选条件
    print(f"\n{Fore.YELLOW}--- 筛选条件设置 ---")

    # 基金类型
    fund_type_str = _input_prompt("基金类型 (如: 股票型,债券型,混合型，留空表示全部)").strip()
    fund_type = [t.strip() for t in fund_type_str.split(",")] if fund_type_str else None

    # 最低收益率
    min_return_str = _input_prompt("近1年最低收益率(%) [留空表示不限]").strip()
    min_return_1y = float(min_return_str) if min_return_str else None

    # 最大回撤限制
    max_dd_str = _input_prompt("最大回撤上限(%) 如 -20 表示允许最多-20% [留空表示不限]").strip()
    max_drawdown = float(max_dd_str) if max_dd_str else None

    # 最低评级
    min_rating_str = _input_prompt("最低星级(1-5) [留空表示不限]").strip()
    min_rating = int(min_rating_str) if min_rating_str else None

    # 返回数量
    top_n_str = _input_prompt("返回前 N 个 [默认 20]").strip()
    top_n = int(top_n_str) if top_n_str else 20

    # 执行筛选
    _print_info("正在筛选...")
    result = analyzer.filter_funds(
        df=df_source,
        fund_type=fund_type,
        min_return_1y=min_return_1y,
        max_drawdown=max_drawdown,
        min_rating=min_rating,
        top_n=top_n
    )

    if result is None or result.empty:
        _print_warning("未找到符合条件的基金，请放宽条件重试")
        return

    _session["filtered"] = result
    _print_success(f"筛选完成，共 {len(result)} 只基金符合条件")
    _print_table(result, title="筛选结果")

    # 保存筛选结果
    if _input_confirm("是否保存筛选结果"):
        output_path = os.path.join(DATA_DIR, "funds_filtered.csv")
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        _print_success(f"已保存到 {output_path}")


# ============================================================
# 菜单 4: 分析单只基金历史净值
# ============================================================

def menu_analyze_single(modules: dict):
    """分析单只基金的历史净值"""
    crawler = modules.get("crawler")
    analyzer = modules.get("analyzer")

    fund_code = _input_prompt("请输入基金代码 (如 000001)").strip()
    if not fund_code:
        _print_error("基金代码不能为空")
        return

    # 可选日期范围
    start_date = _input_prompt("起始日期 (YYYY-MM-DD, 留空=最早)").strip()
    end_date = _input_prompt("结束日期 (YYYY-MM-DD, 留空=最新)").strip()

    _print_info(f"正在爬取基金 {fund_code} 的历史净值...")

    df_history = crawler.get_fund_history(
        fund_code=fund_code,
        start_date=start_date,
        end_date=end_date
    )

    if df_history is None or df_history.empty:
        _print_error(f"未能获取基金 {fund_code} 的历史数据")
        return

    _session["history"][fund_code] = df_history

    _print_success(f"共获取 {len(df_history)} 条历史记录")
    print(f"\n{Fore.CYAN}历史数据预览:")
    print(df_history.head(10).to_string(index=False))

    # 计算收益率统计
    _print_info("正在计算收益率指标...")
    stats = analyzer.calculate_returns(df_history)

    if stats is None:
        _print_warning("收益率计算返回空结果")
    else:
        print(f"\n{Fore.YELLOW}{Style.BRIGHT}基金 {fund_code} 收益统计:{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}总收益率:        {Fore.GREEN if stats.get('total_return', 0) >= 0 else Fore.RED}{stats.get('total_return', 0):.2f}%{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}年化收益率:      {Fore.GREEN if stats.get('annualized_return', 0) >= 0 else Fore.RED}{stats.get('annualized_return', 0):.2f}%{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}波动率:           {stats.get('volatility', 0):.2f}%")
        print(f"  {Fore.WHITE}夏普比率:         {stats.get('sharpe_ratio', 0):.3f}")
        print(f"  {Fore.WHITE}最大回撤:         {Fore.RED}{stats.get('max_drawdown', 0):.2f}%{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}正增长天数:       {Fore.GREEN}{stats.get('positive_days', 0)}{Style.RESET_ALL}")
        print(f"  {Fore.WHITE}负增长天数:       {Fore.RED}{stats.get('negative_days', 0)}{Style.RESET_ALL}")

    # 可选生成走势图
    if _input_confirm("是否生成净值走势图"):
        visualizer = modules.get("visualizer")
        chart_path = os.path.join(CHARTS_DIR, f"net_value_{fund_code}.html")
        visualizer.plot_net_value_trend(fund_code, df_history, chart_path)
        _print_success(f"走势图已生成: {chart_path}")


# ============================================================
# 菜单 5: 对比多只基金
# ============================================================

def menu_compare_funds(modules: dict):
    """对比多只基金的表现"""
    analyzer = modules.get("analyzer")

    codes_str = _input_prompt("请输入基金代码，用空格或逗号分隔 (如 000001,000003,110022)").strip()
    if not codes_str:
        _print_error("基金代码不能为空")
        return

    fund_codes = [c.strip() for c in codes_str.replace(",", " ").split() if c.strip()]
    if len(fund_codes) < 2:
        _print_error("至少需要输入 2 只基金代码进行对比")
        return

    start_date = _input_prompt("起始日期 (YYYY-MM-DD, 留空=默认)").strip()
    end_date = _input_prompt("结束日期 (YYYY-MM-DD, 留空=默认)").strip()

    _print_info(f"正在对比 {len(fund_codes)} 只基金: {', '.join(fund_codes)}")

    compare_df = analyzer.compare_funds(
        fund_codes=fund_codes,
        start_date=start_date,
        end_date=end_date
    )

    if compare_df is None or compare_df.empty:
        _print_error("基金对比失败，请检查基金代码是否正确")
        return

    _session["compare"] = compare_df
    _print_success("对比完成")
    _print_table(compare_df, title="多只基金对比结果")

    # 可选生成对比图
    if _input_confirm("是否生成收益对比图"):
        visualizer = modules.get("visualizer")
        chart_path = os.path.join(CHARTS_DIR, "return_comparison.html")
        visualizer.plot_return_comparison(compare_df, chart_path)
        _print_success(f"对比图已生成: {chart_path}")


# ============================================================
# 菜单 6: 基金相关性分析
# ============================================================

def menu_correlation(modules: dict):
    """多只基金的相关性分析"""
    analyzer = modules.get("analyzer")

    codes_str = _input_prompt("请输入基金代码，用空格或逗号分隔 (至少 2 只)").strip()
    if not codes_str:
        _print_error("基金代码不能为空")
        return

    fund_codes = [c.strip() for c in codes_str.replace(",", " ").split() if c.strip()]
    if len(fund_codes) < 2:
        _print_error("至少需要 2 只基金")
        return

    _print_info(f"正在计算 {len(fund_codes)} 只基金的相关性矩阵...")

    corr_df = analyzer.correlation_analysis(fund_codes)

    if corr_df is None or corr_df.empty:
        _print_error("相关性分析失败")
        return

    _session["correlation"] = corr_df
    _print_success("相关性分析完成")
    _print_table(corr_df, title="基金相关性矩阵")

    # 可选生成热力图
    if _input_confirm("是否生成相关性热力图"):
        visualizer = modules.get("visualizer")
        chart_path = os.path.join(CHARTS_DIR, "correlation_heatmap.html")
        visualizer.plot_correlation_heatmap(corr_df, chart_path)
        _print_success(f"热力图已生成: {chart_path}")


# ============================================================
# 菜单 7: 生成可视化图表
# ============================================================

def menu_visualization(modules: dict):
    """可视化图表子菜单"""
    visualizer = modules.get("visualizer")

    viz_menu = f"""
{Fore.YELLOW}----- 可视化图表菜单 -----

  {Fore.CYAN}1.{Fore.WHITE} 净值走势图   (需先分析单只基金)
  {Fore.CYAN}2.{Fore.WHITE} 收益对比图   (需先进行基金对比)
  {Fore.CYAN}3.{Fore.WHITE} 类型分布饼图 (需基金列表数据)
  {Fore.CYAN}4.{Fore.WHITE} 相关性热力图 (需先进行相关性分析)
  {Fore.CYAN}5.{Fore.WHITE} 增长率分布图 (需历史净值数据)
  {Fore.RED}0.{Fore.WHITE} 返回主菜单
"""
    print(viz_menu)

    choice = _input_prompt("请选择图表类型").strip()

    if choice == "1":
        # 净值走势图
        if not _session["history"]:
            _print_error("暂无历史净值数据，请先执行菜单 4")
            return
        print(f"\n{Fore.CYAN}已缓存的基金: {', '.join(_session['history'].keys())}")
        fund_code = _input_prompt("请输入基金代码").strip()
        df = _session["history"].get(fund_code)
        if df is None:
            _print_error(f"未找到基金 {fund_code} 的历史数据")
            return
        chart_path = os.path.join(CHARTS_DIR, f"net_value_{fund_code}.html")
        visualizer.plot_net_value_trend(fund_code, df, chart_path)

    elif choice == "2":
        # 收益对比图
        if _session["compare"] is None:
            _print_error("暂无对比数据，请先执行菜单 5")
            return
        chart_path = os.path.join(CHARTS_DIR, "return_comparison.html")
        visualizer.plot_return_comparison(_session["compare"], chart_path)

    elif choice == "3":
        # 类型分布饼图
        df_source = None
        if _session["fund_list"] is not None:
            df_source = _session["fund_list"]
        elif _session["ranking"] is not None:
            df_source = _session["ranking"]

        if df_source is None:
            _print_error("暂无基金列表数据，请先执行菜单 1 或 2")
            return

        # 计算类型分布
        analyzer = modules.get("analyzer")
        dist_df = analyzer.fund_type_distribution(df_source)
        if dist_df is None or dist_df.empty:
            _print_error("类型分布计算失败")
            return
        chart_path = os.path.join(CHARTS_DIR, "type_distribution.html")
        visualizer.plot_type_distribution(dist_df, chart_path)

    elif choice == "4":
        # 相关性热力图
        if _session["correlation"] is None:
            _print_error("暂无相关性数据，请先执行菜单 6")
            return
        chart_path = os.path.join(CHARTS_DIR, "correlation_heatmap.html")
        visualizer.plot_correlation_heatmap(_session["correlation"], chart_path)

    elif choice == "5":
        # 增长率分布图
        if not _session["history"]:
            _print_error("暂无历史净值数据，请先执行菜单 4")
            return
        print(f"\n{Fore.CYAN}已缓存的基金: {', '.join(_session['history'].keys())}")
        fund_code = _input_prompt("请输入基金代码 (或输入 all 使用全部)").strip()
        if fund_code.lower() == "all":
            # 合并所有历史数据
            import pandas as pd
            df = pd.concat(_session["history"].values(), ignore_index=True)
        else:
            df = _session["history"].get(fund_code)
            if df is None:
                _print_error(f"未找到基金 {fund_code} 的历史数据")
                return
        chart_path = os.path.join(CHARTS_DIR, f"growth_distribution_{fund_code}.html")
        visualizer.plot_growth_distribution(df, chart_path)

    elif choice == "0":
        return
    else:
        _print_warning("无效选择")


# ============================================================
# 菜单 8: 导出 Excel 报告
# ============================================================

def menu_export_excel(modules: dict):
    """导出数据为 Excel 报告"""
    reporter = modules.get("reporter")

    print(f"\n{Fore.YELLOW}--- 可导出数据 ---")
    options = []

    if _session["fund_list"] is not None:
        print(f"  {Fore.CYAN}1.{Fore.WHITE} 基金列表 ({len(_session['fund_list'])} 条)")
        options.append("fund_list")
    else:
        options.append(None)

    if _session["ranking"] is not None:
        print(f"  {Fore.CYAN}2.{Fore.WHITE} 基金排行 ({len(_session['ranking'])} 条)")
        options.append("ranking")
    else:
        options.append(None)

    if _session["filtered"] is not None:
        print(f"  {Fore.CYAN}3.{Fore.WHITE} 筛选结果 ({len(_session['filtered'])} 条)")
        options.append("filtered")
    else:
        options.append(None)

    if _session["compare"] is not None:
        print(f"  {Fore.CYAN}4.{Fore.WHITE} 对比报告")
        options.append("compare")
    else:
        options.append(None)

    print(f"  {Fore.CYAN}5.{Fore.WHITE} 导出全部到多 sheet 文件")

    choice = _input_prompt("请选择要导出的数据").strip()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if choice == "1" and options[0]:
        filepath = os.path.join(DATA_DIR, f"fund_list_{timestamp}.xlsx")
        reporter.export_fund_list(_session["fund_list"], filepath)
        _print_success(f"基金列表已导出: {filepath}")

    elif choice == "2" and options[1]:
        filepath = os.path.join(DATA_DIR, f"ranking_report_{timestamp}.xlsx")
        reporter.export_ranking_report(_session["ranking"], filepath)
        _print_success(f"排行报告已导出: {filepath}")

    elif choice == "3" and options[2]:
        filepath = os.path.join(DATA_DIR, f"filtered_report_{timestamp}.xlsx")
        reporter.export_fund_list(_session["filtered"], filepath)
        _print_success(f"筛选结果已导出: {filepath}")

    elif choice == "4" and options[3]:
        filepath = os.path.join(DATA_DIR, f"comparison_report_{timestamp}.xlsx")
        reporter.export_comparison_report(_session["compare"], filepath)
        _print_success(f"对比报告已导出: {filepath}")

    elif choice == "5":
        # 导出多 sheet 文件
        filepath = os.path.join(DATA_DIR, f"full_report_{timestamp}.xlsx")
        import pandas as pd
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            sheet_count = 0
            if _session["fund_list"] is not None:
                _session["fund_list"].to_excel(writer, sheet_name="基金列表", index=False)
                sheet_count += 1
            if _session["ranking"] is not None:
                _session["ranking"].to_excel(writer, sheet_name="基金排行", index=False)
                sheet_count += 1
            if _session["filtered"] is not None:
                _session["filtered"].to_excel(writer, sheet_name="筛选结果", index=False)
                sheet_count += 1
            if _session["compare"] is not None:
                _session["compare"].to_excel(writer, sheet_name="基金对比", index=True)
                sheet_count += 1
            if _session["correlation"] is not None:
                _session["correlation"].to_excel(writer, sheet_name="相关性矩阵", index=True)
                sheet_count += 1

        if sheet_count > 0:
            _print_success(f"综合报告已导出 ({sheet_count} 个 sheet): {filepath}")
        else:
            _print_warning("当前没有可导出的数据")

    else:
        _print_warning("无效选择或对应数据为空")


# ============================================================
# 菜单 9: 一键综合分析
# ============================================================

def menu_full_analysis(modules: dict):
    """
    一键综合分析流程:
    1. 爬取排行 TOP20
    2. 逐只分析
    3. 导出 Excel
    4. 生成全部图表
    """
    crawler = modules.get("crawler")
    analyzer = modules.get("analyzer")
    visualizer = modules.get("visualizer")
    reporter = modules.get("reporter")

    _print_info("=" * 50)
    _print_info("开始一键综合分析...")
    _print_info("=" * 50)

    # ---- 第1步: 爬取排行 TOP20 ----
    print(f"\n{Fore.YELLOW}[1/4] 爬取基金排行 TOP20...")
    ranking_df = crawler.get_fund_ranking(top_n=20)

    if ranking_df is None or ranking_df.empty:
        _print_error("爬取排行失败，终止分析")
        return

    _session["ranking"] = ranking_df
    _print_success(f"成功获取 TOP{len(ranking_df)} 基金排行")

    # 保存排行
    ranking_path = os.path.join(DATA_DIR, "funds_ranking.csv")
    ranking_df.to_csv(ranking_path, index=False, encoding="utf-8-sig")

    # ---- 第2步: 逐只分析 ----
    print(f"\n{Fore.YELLOW}[2/4] 逐只分析基金...")

    # 获取基金代码列表
    fund_codes = []
    for col in ["基金代码", "fund_code", "代码"]:
        if col in ranking_df.columns:
            fund_codes = ranking_df[col].astype(str).tolist()
            break

    if not fund_codes:
        # 尝试用索引
        fund_codes = [str(idx) for idx in ranking_df.index[:20]]

    analysis_results = []
    history_map = {}

    for i, code in enumerate(fund_codes[:20]):
        print(f"  {Fore.CYAN}[{i+1:2d}/20] 分析基金 {code}...", end=" ")
        try:
            df_his = crawler.get_fund_history(fund_code=code)
            if df_his is not None and not df_his.empty:
                history_map[code] = df_his
                stats = analyzer.calculate_returns(df_his)
                if stats:
                    stats["基金代码"] = code
                    # 尝试获取基金名称
                    name = ""
                    for col in ["基金简称", "基金名称"]:
                        if col in ranking_df.columns:
                            name = ranking_df[ranking_df.iloc[:, 0].astype(str) == code][col].values
                            if len(name) > 0:
                                name = str(name[0])
                                break
                    stats["基金名称"] = name
                    analysis_results.append(stats)
                    print(f"{Fore.GREEN}完成 ({len(df_his)} 条)")
                else:
                    print(f"{Fore.YELLOW}无统计结果")
            else:
                print(f"{Fore.RED}无数据")
        except Exception as e:
            print(f"{Fore.RED}失败: {str(e)[:40]}")

        time.sleep(0.3)  # 请求间隔

    _session["history"].update(history_map)
    _print_success(f"完成 {len(analysis_results)} 只基金的分析")

    # ---- 第3步: 导出 Excel ----
    print(f"\n{Fore.YELLOW}[3/4] 导出 Excel 报告...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    import pandas as pd
    report_path = os.path.join(DATA_DIR, f"full_analysis_{timestamp}.xlsx")

    try:
        with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
            # Sheet 1: 排行
            ranking_df.to_excel(writer, sheet_name="排行数据", index=False)

            # Sheet 2: 分析统计
            if analysis_results:
                stats_df = pd.DataFrame(analysis_results)
                stats_df.to_excel(writer, sheet_name="收益统计", index=False)

            # Sheet 3: 类型分布
            dist_df = analyzer.fund_type_distribution(ranking_df)
            if dist_df is not None and not dist_df.empty:
                dist_df.to_excel(writer, sheet_name="类型分布", index=False)

        _print_success(f"Excel 报告已导出: {report_path}")
    except Exception as e:
        _print_error(f"Excel 导出失败: {e}")

    # ---- 第4步: 生成图表 ----
    print(f"\n{Fore.YELLOW}[4/4] 生成可视化图表...")

    # 类型分布饼图
    if dist_df is not None and not dist_df.empty:
        try:
            visualizer.plot_type_distribution(
                dist_df,
                os.path.join(CHARTS_DIR, "type_distribution.html")
            )
        except Exception as e:
            _print_warning(f"类型分布图生成失败: {e}")

    # 相关性分析 (取前10只有历史数据的基金)
    codes_with_data = list(history_map.keys())[:10]
    if len(codes_with_data) >= 2:
        try:
            print(f"  {Fore.CYAN}计算 {len(codes_with_data)} 只基金的相关性...")
            corr_df = analyzer.correlation_analysis(codes_with_data)
            if corr_df is not None and not corr_df.empty:
                _session["correlation"] = corr_df
                visualizer.plot_correlation_heatmap(
                    corr_df,
                    os.path.join(CHARTS_DIR, "correlation_heatmap.html")
                )
        except Exception as e:
            _print_warning(f"相关性分析失败: {e}")

    # 净值走势图（前5只）
    for i, code in enumerate(codes_with_data[:5]):
        try:
            visualizer.plot_net_value_trend(
                code,
                history_map[code],
                os.path.join(CHARTS_DIR, f"net_value_{code}.html")
            )
        except Exception as e:
            _print_warning(f"基金 {code} 走势图失败: {e}")

    # 增长率分布图（前3只）
    for i, code in enumerate(codes_with_data[:3]):
        try:
            visualizer.plot_growth_distribution(
                history_map[code],
                os.path.join(CHARTS_DIR, f"growth_{code}.html")
            )
        except Exception as e:
            _print_warning(f"基金 {code} 分布图失败: {e}")

    _print_success("一键综合分析全部完成！")
    print(f"\n{Fore.GREEN}生成文件清单:")
    print(f"  {Fore.WHITE}Excel: {report_path}")
    print(f"  {Fore.WHITE}图表目录: {CHARTS_DIR}")


# ============================================================
# 主循环
# ============================================================

def main():
    """主程序入口"""
    parser = argparse.ArgumentParser(description="基金分析工具")
    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="自动运行一键综合分析后退出"
    )
    args = parser.parse_args()

    _clear_screen()
    _print_banner()

    # 导入核心模块
    modules = _import_core_modules()

    if args.auto:
        # 自动模式: 直接运行一键综合分析
        menu_full_analysis(modules)
        return

    # 交互模式: 主循环
    while True:
        _print_menu()
        choice = _input_prompt("请输入选项编号").strip()

        if choice == "0":
            print(f"\n{Fore.GREEN}感谢使用基金分析工具，再见！{Style.RESET_ALL}")
            break

        elif choice == "1":
            _clear_screen()
            _print_banner()
            try:
                menu_crawl_fund_list(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "2":
            _clear_screen()
            _print_banner()
            try:
                menu_view_ranking(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "3":
            _clear_screen()
            _print_banner()
            try:
                menu_filter_funds(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "4":
            _clear_screen()
            _print_banner()
            try:
                menu_analyze_single(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "5":
            _clear_screen()
            _print_banner()
            try:
                menu_compare_funds(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "6":
            _clear_screen()
            _print_banner()
            try:
                menu_correlation(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "7":
            _clear_screen()
            _print_banner()
            try:
                menu_visualization(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "8":
            _clear_screen()
            _print_banner()
            try:
                menu_export_excel(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        elif choice == "9":
            _clear_screen()
            _print_banner()
            try:
                menu_full_analysis(modules)
            except Exception as e:
                _print_error(f"操作失败: {e}")
            _wait_continue()
            _clear_screen()
            _print_banner()

        else:
            _print_warning(f"无效选项: '{choice}'，请重新输入")


if __name__ == "__main__":
    main()
