#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金分析工具 —— GUI 图形界面（修复版）
基于 tkinter + ttk 的现代化界面，支持所有 CLI 功能

修复内容：
  1. 修复 DataFrame 布尔值导致的 ValueError（pandas 的 truth value ambiguous）
  2. 修复回调函数异常在主线程中未被捕获的问题
  3. 优化 Treeview 列宽自适应，避免内容被截断
  4. 限制 Treeview 显示行数，大数据量不再卡顿
  5. 优化一键分析日志，减少 tkinter 事件队列拥堵
  6. 增强筛选条件对缺失列的容错提示

用法:
    python gui.py              # 启动 GUI
"""

import re
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import traceback
import os
import sys
import platform
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

# ============================================================
# 项目路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CHARTS_DIR = os.path.join(BASE_DIR, "charts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

# 导入核心模块
try:
    from core import crawler, analyzer, visualizer, reporter
    CORE_MODULES_LOADED = True
except ImportError as e:
    CORE_MODULES_LOADED = False
    print(f"[警告] 核心模块导入失败: {e}")

try:
    import pandas as pd
    import numpy as np
except ImportError:
    CORE_MODULES_LOADED = False
    print("[警告] pandas 或 numpy 未安装")

# ============================================================
# 全局会话状态
# ============================================================
_session = {
    "fund_list": None,
    "ranking": None,
    "filtered": None,
    "history": {},
    "compare": None,
    "correlation": None,
}

# 映射字典
FUND_TYPE_MAP = {
    "全部": "all", "股票型": "gp", "债券型": "zq",
    "混合型": "hh", "指数型": "zs", "QDII": "qdii",
    "货币型": "hb", "FOF": "fof", "短期理财": "lc",
}

SORT_BY_MAP = {
    "近1月": "1nzf", "近3月": "3nzf", "近6月": "6nzf",
    "近1年": "1y", "近2年": "2y", "近3年": "3y",
    "今年来": "jnyl", "成立来": "cll",
}

DATE_RANGE_MAP = {
    "近1年": "1y", "近3年": "3y", "近5年": "5y",
}


# ============================================================
# 安全工具函数
# ============================================================

def _safe_get_df(key1, key2=None):
    """
    安全地从 _session 获取 DataFrame。
    避免 pandas DataFrame 的 "truth value ambiguous" 错误。
    """
    df = _session.get(key1)
    if df is not None and not df.empty:
        return df
    if key2:
        df = _session.get(key2)
        if df is not None and not df.empty:
            return df
    return None


# ============================================================
# GUI 主类
# ============================================================
class FundAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("基金分析工具 v1.0")
        self.root.geometry("1500x950")
        self.root.minsize(1200, 750)
        self.root.configure(bg="#f0f2f5")

        # 自定义样式
        self._setup_styles()

        # 主框架
        self.main_frame = tk.Frame(root, bg="#f0f2f5")
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._create_sidebar()
        self._create_main_area()
        self._create_status_bar()

        self.pages = {}
        self._progress = {}
        self._build_pages()

        self._show_page("home")

        if not CORE_MODULES_LOADED:
            self._set_status("警告：核心模块未加载，部分功能不可用")
            messagebox.showwarning(
                "模块加载",
                "核心模块导入失败，请检查依赖安装\n\n"
                "pip install -r requirements.txt"
            )

    # ==================== 界面构建 ====================

    def _setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Data.Treeview", font=("Microsoft YaHei", 9), rowheight=24)
        self.style.configure("Data.Treeview.Heading", font=("Microsoft YaHei", 9, "bold"))
        self.style.configure("Panel.TLabelframe", font=("Microsoft YaHei", 10, "bold"))
        self.style.configure("Panel.TLabelframe.Label", font=("Microsoft YaHei", 10, "bold"))
        self.style.configure("Progress.Horizontal.TProgressbar", thickness=8, background="#2c5aa0")

    def _create_sidebar(self):
        self.sidebar = tk.Frame(self.main_frame, width=220, bg="#2c3e50", relief=tk.FLAT)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="基金分析工具", font=("Microsoft YaHei", 16, "bold"), fg="#ecf0f1", bg="#2c3e50").pack(pady=(20, 5))
        tk.Label(self.sidebar, text="v1.0", font=("Microsoft YaHei", 10), fg="#bdc3c7", bg="#2c3e50").pack()

        tk.Frame(self.sidebar, height=2, bg="#34495e").pack(fill=tk.X, padx=15, pady=10)

        self.nav_buttons = {}
        nav_items = [
            ("home", "首页"),
            ("crawl", "爬取基金列表"),
            ("ranking", "查看基金排行"),
            ("filter", "筛选优质基金"),
            ("analyze", "分析单只基金"),
            ("compare", "对比多只基金"),
            ("correlation", "相关性分析"),
            ("visualize", "生成可视化图表"),
            ("export", "导出 Excel 报告"),
            ("full", "一键综合分析"),
        ]
        for key, text in nav_items:
            btn = tk.Button(self.sidebar, text=text, font=("Microsoft YaHei", 10), bg="#34495e", fg="#ecf0f1",
                            activebackground="#2c5aa0", activeforeground="#fff", bd=0, padx=10, pady=8,
                            cursor="hand2", anchor="w", relief=tk.FLAT,
                            command=lambda k=key: self._show_page(k))
            btn.pack(fill=tk.X, padx=10, pady=2)
            self.nav_buttons[key] = btn

        tk.Frame(self.sidebar, height=2, bg="#34495e").pack(fill=tk.X, padx=15, pady=10)
        tk.Button(self.sidebar, text="退出程序", font=("Microsoft YaHei", 10), bg="#e74c3c", fg="#fff",
                  activebackground="#c0392b", bd=0, padx=10, pady=8, cursor="hand2",
                  command=self.root.quit).pack(fill=tk.X, padx=10, pady=5)

    def _create_main_area(self):
        self.content_frame = tk.Frame(self.main_frame, bg="#ffffff", relief=tk.FLAT, bd=2)
        self.content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

    def _create_status_bar(self):
        self.status_bar = tk.Label(self.root, text="就绪", font=("Microsoft YaHei", 9), bg="#ecf0f1", fg="#2c3e50",
                                   relief=tk.SUNKEN, anchor=tk.W, bd=1, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _create_page_progress(self, page, key):
        """为指定页面创建百分比进度条（放在按钮和数据区之间）"""
        frame = tk.Frame(page, bg="#fff")
        frame.pack(fill=tk.X, padx=15, pady=(0, 5))
        var = tk.DoubleVar(value=0)
        self._progress[key] = {"var": var, "frame": frame, "timer": None}
        bar = ttk.Progressbar(frame, variable=var, maximum=100, mode="determinate", length=500, style="Progress.Horizontal.TProgressbar")
        bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        label = tk.Label(frame, text="0%", font=("Microsoft YaHei", 9), bg="#fff", fg="#2c5aa0", width=5)
        label.pack(side=tk.RIGHT, padx=(5, 0))
        self._progress[key]["label"] = label

    def _set_progress(self, key, value):
        """安全设置进度条值（0-100）"""
        if key not in self._progress:
            return
        value = max(0, min(100, value))
        self._progress[key]["var"].set(value)
        self._progress[key]["label"].config(text=f"{value:.0f}%")

    def _start_progress(self, key):
        """启动模拟递增进度（适用于网络请求等无法精确计算的操作）"""
        self._set_progress(key, 0)
        def step():
            if key not in self._progress:
                return
            current = self._progress[key]["var"].get()
            if current < 90:
                delta = max(0.5, (95 - current) / 30)
                self._set_progress(key, min(current + delta, 90))
                self._progress[key]["timer"] = self.root.after(150, step)
        step()

    def _stop_progress(self, key, success=True):
        """停止进度条，成功时设为100%，失败时设为0%"""
        if key not in self._progress:
            return
        timer = self._progress[key].get("timer")
        if timer is not None:
            try:
                self.root.after_cancel(timer)
            except Exception:
                pass
            self._progress[key]["timer"] = None
        self._set_progress(key, 100 if success else 0)

    def _build_pages(self):
        self._build_home_page()
        self._build_crawl_page()
        self._build_ranking_page()
        self._build_filter_page()
        self._build_analyze_page()
        self._build_compare_page()
        self._build_correlation_page()
        self._build_visualize_page()
        self._build_export_page()
        self._build_full_page()

    def _show_page(self, page_name):
        for name, page in self.pages.items():
            if name == page_name:
                page.pack(fill=tk.BOTH, expand=True)
            else:
                page.pack_forget()
        self._set_status(f"当前页面: {self._get_page_title(page_name)}")

    def _get_page_title(self, page_name):
        titles = {
            "home": "首页", "crawl": "爬取基金列表", "ranking": "查看基金排行",
            "filter": "筛选优质基金", "analyze": "分析单只基金",
            "compare": "对比多只基金", "correlation": "相关性分析",
            "visualize": "生成可视化图表", "export": "导出 Excel 报告",
            "full": "一键综合分析",
        }
        return titles.get(page_name, page_name)

    # ==================== 辅助方法 ====================

    def _set_status(self, msg):
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} | {msg}")

    def _display_dataframe(self, df, tree, max_rows=200):
        """将 DataFrame 显示到 Treeview，自适应列宽，限制行数。"""
        for item in tree.get_children():
            tree.delete(item)

        if df is None or df.empty:
            tree["columns"] = []
            tree["show"] = "headings"
            return

        columns = list(df.columns)
        tree["columns"] = columns
        tree["show"] = "headings"

        # 自适应列宽：基于标题 + 前 50 行数据长度
        for col in columns:
            header_len = len(str(col))
            max_data_len = 0
            sample = df[col].head(50)
            for val in sample:
                val_len = len(str(val))
                if val_len > max_data_len:
                    max_data_len = val_len
            width = max(header_len, max_data_len) * 9 + 20
            width = max(min(width, 280), 60)  # 60 ~ 280 px
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor=tk.CENTER, minwidth=50)

        # 限制显示行数，避免大数据量卡顿
        display_df = df.head(max_rows)
        for _, row in display_df.iterrows():
            values = [str(v) for v in row.values]
            tree.insert("", tk.END, values=values)

        total = len(df)
        shown = len(display_df)
        if total > shown:
            self._set_status(f"数据共 {total} 行，当前显示前 {shown} 行")
        else:
            self._set_status(f"数据共 {total} 行")

    def _run_async(self, target, args=(), callback=None, page_key=None):
        """在后台线程中执行函数，callback 安全地回到主线程。支持进度条。"""
        if page_key:
            self._start_progress(page_key)
        def wrapper():
            try:
                result = target(*args)
                if callback:
                    def safe_callback():
                        try:
                            callback(result)
                        except Exception as cb_err:
                            err_msg = f"回调异常: {str(cb_err)}"
                            traceback_str = traceback.format_exc()
                            print(traceback_str)
                            self._show_error(err_msg)
                        finally:
                            if page_key:
                                self._stop_progress(page_key, success=True)
                    self.root.after(0, safe_callback)
            except Exception as e:
                traceback_str = traceback.format_exc()
                print(traceback_str)
                def error_callback():
                    self._show_error(f"后台任务异常: {str(e)}")
                    if page_key:
                        self._stop_progress(page_key, success=False)
                self.root.after(0, error_callback)

        self._set_status("正在执行...")
        t = threading.Thread(target=wrapper)
        t.daemon = True
        t.start()

    def _show_error(self, msg):
        messagebox.showerror("错误", msg)
        self._set_status("执行出错")

    def _show_info(self, msg):
        messagebox.showinfo("提示", msg)

    def _create_dataframe_viewer(self, parent):
        """创建 DataFrame 查看器（Treeview + Scrollbar + 行数提示）"""
        outer = tk.Frame(parent, bg="#fff")
        outer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        frame = tk.Frame(outer, bg="#fff")
        frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(frame, style="Data.Treeview", show="headings")
        tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        tree.configure(xscrollcommand=hsb.set)

        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return tree

    def _open_dir(self, path):
        abs_path = os.path.abspath(path)
        if platform.system() == "Windows":
            os.startfile(abs_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", abs_path])
        else:
            subprocess.Popen(["xdg-open", abs_path])

    # ==================== 页面 1: 首页 ====================

    def _build_home_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["home"] = page

        center = tk.Frame(page, bg="#fff")
        center.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        tk.Label(center, text="欢迎使用基金分析工具", font=("Microsoft YaHei", 28, "bold"), bg="#fff", fg="#2c3e50").pack(pady=10)
        tk.Label(center, text="从天天基金网爬取数据 · 筛选 · 分析 · 可视化", font=("Microsoft YaHei", 14), bg="#fff", fg="#7f8c8d").pack(pady=10)

        info = tk.Frame(center, bg="#fff")
        info.pack(pady=30)
        tk.Label(info, text="功能概览", font=("Microsoft YaHei", 12, "bold"), bg="#fff", fg="#2c3e50").pack(anchor=tk.W, pady=5)
        features = [
            "1. 爬取基金列表 — 获取全部基金基础信息",
            "2. 查看基金排行 — 按收益率等多维度排序",
            "3. 筛选优质基金 — 按类型、收益、回撤、评级等条件筛选",
            "4. 分析单只基金 — 历史净值走势、收益统计、波动率、夏普比率",
            "5. 对比多只基金 — 横向对比收益与风险指标",
            "6. 相关性分析 — 计算日增长率相关性矩阵",
            "7. 生成可视化图表 — 净值走势、对比图、饼图、热力图",
            "8. 导出 Excel 报告 — 多 Sheet 综合分析报告",
            "9. 一键综合分析 — 自动爬取、分析、导出、生成图表",
        ]
        for f in features:
            tk.Label(info, text=f, font=("Microsoft YaHei", 10), bg="#fff", fg="#555", anchor=tk.W).pack(anchor=tk.W, pady=2)

    # ==================== 页面 2: 爬取基金列表 ====================

    def _build_crawl_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["crawl"] = page

        tk.Label(page, text="爬取基金列表", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)
        tk.Label(page, text="从天天基金网获取全部基金基础信息（约26000+只基金）", font=("Microsoft YaHei", 10), bg="#fff", fg="#7f8c8d").pack()

        btn = tk.Button(page, text="开始爬取", font=("Microsoft YaHei", 11, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=20, pady=8, command=self._do_crawl)
        btn.pack(pady=15)

        self._create_page_progress(page, "crawl")

        self.crawl_tree = self._create_dataframe_viewer(page)

    def _do_crawl(self):
        def crawl():
            if not CORE_MODULES_LOADED:
                return None
            df = crawler.get_fund_list()
            _session["fund_list"] = df
            if df is not None and not df.empty:
                path = os.path.join(DATA_DIR, "funds_list.csv")
                df.to_csv(path, index=False, encoding="utf-8-sig")
            return df

        def on_done(df):
            if df is None:
                self._show_error("爬取失败，请检查网络连接")
                return
            self._display_dataframe(df, self.crawl_tree)
            self._show_info(f"共爬取 {len(df)} 只基金，已保存到 data/funds_list.csv")

        self._run_async(crawl, callback=on_done, page_key="crawl")

    # ==================== 页面 3: 基金排行 ====================

    def _build_ranking_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["ranking"] = page

        tk.Label(page, text="基金排行 TOP100", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="查询条件", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(ctrl_frame, text="基金类型:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.E)
        self.ranking_type = ttk.Combobox(ctrl_frame, values=["全部", "股票型", "债券型", "混合型", "指数型", "QDII", "货币型", "FOF"], width=12, font=("Microsoft YaHei", 10))
        self.ranking_type.set("全部")
        self.ranking_type.grid(row=0, column=1, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="排序方式:", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=5, pady=8, sticky=tk.E)
        self.ranking_sort = ttk.Combobox(ctrl_frame, values=["近1月", "近3月", "近6月", "近1年", "近2年", "近3年", "今年来", "成立来"], width=12, font=("Microsoft YaHei", 10))
        self.ranking_sort.set("近1年")
        self.ranking_sort.grid(row=0, column=3, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="时间段:", font=("Microsoft YaHei", 10)).grid(row=0, column=4, padx=5, pady=8, sticky=tk.E)
        self.ranking_range = ttk.Combobox(ctrl_frame, values=["近1年", "近3年", "近5年"], width=12, font=("Microsoft YaHei", 10))
        self.ranking_range.set("近1年")
        self.ranking_range.grid(row=0, column=5, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="显示数量:", font=("Microsoft YaHei", 10)).grid(row=0, column=6, padx=5, pady=8, sticky=tk.E)
        self.ranking_top = ttk.Spinbox(ctrl_frame, from_=10, to=500, width=8, font=("Microsoft YaHei", 10))
        self.ranking_top.set(100)
        self.ranking_top.grid(row=0, column=7, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="查询", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_ranking)
        btn.grid(row=0, column=8, padx=10, pady=8)

        export_btn = tk.Button(ctrl_frame, text="导出CSV", font=("Microsoft YaHei", 10), bg="#27ae60", fg="#fff",
                               activebackground="#1e8449", cursor="hand2", bd=0, padx=10, pady=5, command=self._export_ranking)
        export_btn.grid(row=0, column=9, padx=5, pady=8)

        self._create_page_progress(page, "ranking")

        self.ranking_tree = self._create_dataframe_viewer(page)

    def _do_ranking(self):
        def fetch():
            if not CORE_MODULES_LOADED:
                return None
            fund_type = FUND_TYPE_MAP.get(self.ranking_type.get(), "all")
            sort_by = SORT_BY_MAP.get(self.ranking_sort.get(), "1y")
            date_range = DATE_RANGE_MAP.get(self.ranking_range.get(), "1y")
            try:
                top_n = int(self.ranking_top.get())
            except:
                top_n = 100

            df = crawler.get_fund_ranking(
                fund_type=fund_type, sort_by=sort_by, top_n=top_n, date_range=date_range
            )
            _session["ranking"] = df
            return df

        def on_done(df):
            if df is None or df.empty:
                self._show_error("获取排行数据失败")
                return
            self._display_dataframe(df, self.ranking_tree)
            self._show_info(f"共获取 {len(df)} 条排行数据")

        self._run_async(fetch, callback=on_done, page_key="ranking")

    def _export_ranking(self):
        df = _session.get("ranking")
        if df is None or df.empty:
            self._show_error("没有排行数据可导出")
            return
        path = os.path.join(DATA_DIR, "funds_ranking.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        self._show_info(f"已导出到 {path}")

    # ==================== 页面 4: 筛选优质基金 ====================

    def _build_filter_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["filter"] = page

        tk.Label(page, text="筛选优质基金", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="筛选条件", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(ctrl_frame, text="基金类型:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.E)
        self.filter_type = ttk.Combobox(ctrl_frame, values=["全部", "股票型", "债券型", "混合型", "指数型", "QDII", "货币型", "FOF"], width=12, font=("Microsoft YaHei", 10))
        self.filter_type.set("全部")
        self.filter_type.grid(row=0, column=1, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="最低收益率(%):", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=5, pady=8, sticky=tk.E)
        self.filter_return = ttk.Entry(ctrl_frame, width=10, font=("Microsoft YaHei", 10))
        self.filter_return.insert(0, "")
        self.filter_return.grid(row=0, column=3, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="最大回撤上限(%):", font=("Microsoft YaHei", 10)).grid(row=0, column=4, padx=5, pady=8, sticky=tk.E)
        self.filter_drawdown = ttk.Entry(ctrl_frame, width=10, font=("Microsoft YaHei", 10))
        self.filter_drawdown.insert(0, "")
        self.filter_drawdown.grid(row=0, column=5, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="最低星级:", font=("Microsoft YaHei", 10)).grid(row=0, column=6, padx=5, pady=8, sticky=tk.E)
        self.filter_rating = ttk.Combobox(ctrl_frame, values=["不限", "1", "2", "3", "4", "5"], width=8, font=("Microsoft YaHei", 10))
        self.filter_rating.set("不限")
        self.filter_rating.grid(row=0, column=7, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="返回数量:", font=("Microsoft YaHei", 10)).grid(row=0, column=8, padx=5, pady=8, sticky=tk.E)
        self.filter_top = ttk.Spinbox(ctrl_frame, from_=10, to=500, width=8, font=("Microsoft YaHei", 10))
        self.filter_top.set(50)
        self.filter_top.grid(row=0, column=9, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="开始筛选", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_filter)
        btn.grid(row=0, column=10, padx=10, pady=8)

        save_btn = tk.Button(ctrl_frame, text="保存结果", font=("Microsoft YaHei", 10), bg="#27ae60", fg="#fff",
                             activebackground="#1e8449", cursor="hand2", bd=0, padx=10, pady=5, command=self._save_filter)
        save_btn.grid(row=0, column=11, padx=5, pady=8)

        # 提示标签
        self.filter_hint = tk.Label(page, text="", font=("Microsoft YaHei", 9), bg="#fff", fg="#e74c3c", anchor=tk.W)
        self.filter_hint.pack(fill=tk.X, padx=15)

        self._create_page_progress(page, "filter")

        self.filter_tree = self._create_dataframe_viewer(page)

    def _do_filter(self):
        def do_filter():
            if not CORE_MODULES_LOADED:
                return None

            # 安全获取数据源（修复 DataFrame 布尔值问题）
            df_source = _safe_get_df("ranking", "fund_list")
            if df_source is None:
                # 尝试加载本地文件
                ranking_path = os.path.join(DATA_DIR, "funds_ranking.csv")
                list_path = os.path.join(DATA_DIR, "funds_list.csv")
                if os.path.exists(ranking_path):
                    df_source = pd.read_csv(ranking_path)
                    _session["ranking"] = df_source
                elif os.path.exists(list_path):
                    df_source = pd.read_csv(list_path)
                    _session["fund_list"] = df_source
                else:
                    return "no_data"

            fund_type = self.filter_type.get()
            fund_type = None if fund_type == "全部" else [fund_type]

            min_return = self.filter_return.get().strip()
            min_return = float(min_return) if min_return else None

            max_dd = self.filter_drawdown.get().strip()
            max_drawdown = float(max_dd) if max_dd else None

            rating = self.filter_rating.get()
            min_rating = int(rating) if rating != "不限" else None

            try:
                top_n = int(self.filter_top.get())
            except:
                top_n = 50

            # 检查数据源是否包含基金类型列（排行数据缺少此列）
            has_type_col = any(c in df_source.columns for c in ["基金类型", "类型", "fund_type"])
            type_skipped = False
            if fund_type is not None and not has_type_col:
                type_skipped = True
                fund_type = None  # 忽略类型过滤，避免 filter_funds 找不到列而报错

            result = analyzer.filter_funds(
                df=df_source, fund_type=fund_type, min_return_1y=min_return,
                max_drawdown=max_drawdown, min_rating=min_rating, top_n=top_n
            )
            _session["filtered"] = result
            return {"result": result, "type_skipped": type_skipped}

        def on_done(data):
            if data == "no_data":
                self._show_error("没有可用数据，请先执行爬取或排行查询")
                return
            if data is None:
                self._show_error("筛选失败")
                return

            result = data.get("result")
            type_skipped = data.get("type_skipped", False)

            if type_skipped:
                self.filter_hint.config(text="提示：当前数据源（排行数据）缺少基金类型列，类型筛选已自动忽略。")
            else:
                self.filter_hint.config(text="")

            if result is None or result.empty:
                self._show_info("未找到符合条件的基金，请放宽条件重试")
                return

            self._display_dataframe(result, self.filter_tree)
            self._show_info(f"筛选完成，共 {len(result)} 只基金符合条件")

        self._run_async(do_filter, callback=on_done, page_key="filter")

    def _save_filter(self):
        df = _session.get("filtered")
        if df is None or df.empty:
            self._show_error("没有筛选结果可保存")
            return
        path = os.path.join(DATA_DIR, "funds_filtered.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        self._show_info(f"已保存到 {path}")

    # ==================== 页面 5: 分析单只基金 ====================

    def _build_analyze_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["analyze"] = page

        tk.Label(page, text="分析单只基金历史净值", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="查询参数", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(ctrl_frame, text="基金代码:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.E)
        self.analyze_code = ttk.Entry(ctrl_frame, width=15, font=("Microsoft YaHei", 10))
        self.analyze_code.insert(0, "000001")
        self.analyze_code.grid(row=0, column=1, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="起始日期:", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=5, pady=8, sticky=tk.E)
        self.analyze_start = ttk.Entry(ctrl_frame, width=12, font=("Microsoft YaHei", 10))
        self.analyze_start.grid(row=0, column=3, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="结束日期:", font=("Microsoft YaHei", 10)).grid(row=0, column=4, padx=5, pady=8, sticky=tk.E)
        self.analyze_end = ttk.Entry(ctrl_frame, width=12, font=("Microsoft YaHei", 10))
        self.analyze_end.grid(row=0, column=5, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="开始分析", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_analyze)
        btn.grid(row=0, column=6, padx=10, pady=8)

        chart_btn = tk.Button(ctrl_frame, text="生成走势图", font=("Microsoft YaHei", 10), bg="#8e44ad", fg="#fff",
                              activebackground="#6c3483", cursor="hand2", bd=0, padx=10, pady=5, command=self._do_analyze_chart)
        chart_btn.grid(row=0, column=7, padx=5, pady=8)

        stats_frame = ttk.LabelFrame(page, text="收益统计", style="Panel.TLabelframe")
        stats_frame.pack(fill=tk.X, padx=15, pady=5)
        self.stats_text = tk.Text(stats_frame, height=8, wrap=tk.WORD, font=("Consolas", 11), bg="#fafafa", relief=tk.FLAT, bd=2)
        self.stats_text.pack(fill=tk.X, padx=5, pady=5)

        self._create_page_progress(page, "analyze")

        self.analyze_tree = self._create_dataframe_viewer(page)

    def _do_analyze(self):
        def analyze():
            if not CORE_MODULES_LOADED:
                return None
            code = self.analyze_code.get().strip()
            if not code:
                return "no_code"
            start = self.analyze_start.get().strip()
            end = self.analyze_end.get().strip()

            df = crawler.get_fund_history(code, start, end)
            if df is None or df.empty:
                return "no_data"

            _session["history"][code] = df
            stats = analyzer.calculate_returns(df)
            return {"code": code, "df": df, "stats": stats}

        def on_done(result):
            if result == "no_code":
                self._show_error("请输入基金代码")
                return
            if result == "no_data":
                self._show_error("未能获取历史数据")
                return
            if result is None:
                self._show_error("分析失败")
                return

            code = result["code"]
            df = result["df"]
            stats = result["stats"]

            self._display_dataframe(df, self.analyze_tree)

            self.stats_text.delete(1.0, tk.END)
            lines = [
                f"基金 {code} 收益统计:",
                f"  总收益率:      {stats.get('total_return', 0):.2f}%",
                f"  年化收益率:    {stats.get('annualized_return', 0):.2f}%",
                f"  波动率:        {stats.get('volatility', 0):.2f}%",
                f"  夏普比率:      {stats.get('sharpe_ratio', 0):.3f}",
                f"  最大回撤:      {stats.get('max_drawdown', 0):.2f}%",
                f"  正增长天数:    {stats.get('positive_days', 0)}",
                f"  负增长天数:    {stats.get('negative_days', 0)}",
            ]
            text = chr(10).join(lines) + chr(10)
            self.stats_text.insert(tk.END, text)
            self._set_status(f"分析完成，共 {len(df)} 条历史记录")

        self._run_async(analyze, callback=on_done, page_key="analyze")

    def _do_analyze_chart(self):
        code = self.analyze_code.get().strip()
        if not code or code not in _session["history"]:
            self._show_error("请先进行分析获取历史数据")
            return
        df = _session["history"][code]
        path = os.path.join(CHARTS_DIR, f"net_value_{code}.html")
        try:
            visualizer.plot_net_value_trend(code, df, path)
            self._set_status(f"走势图已生成: {path}")
            webbrowser.open(Path(path).as_uri())
        except Exception as e:
            self._show_error(f"生成图表失败: {e}")

    # ==================== 页面 6: 对比多只基金 ====================

    def _build_compare_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["compare"] = page

        tk.Label(page, text="对比多只基金", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="对比参数", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(ctrl_frame, text="基金代码(逗号分隔):", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.E)
        self.compare_codes = ttk.Entry(ctrl_frame, width=40, font=("Microsoft YaHei", 10))
        self.compare_codes.insert(0, "000001,110022,161725")
        self.compare_codes.grid(row=0, column=1, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="起始日期:", font=("Microsoft YaHei", 10)).grid(row=0, column=2, padx=5, pady=8, sticky=tk.E)
        self.compare_start = ttk.Entry(ctrl_frame, width=12, font=("Microsoft YaHei", 10))
        self.compare_start.grid(row=0, column=3, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="结束日期:", font=("Microsoft YaHei", 10)).grid(row=0, column=4, padx=5, pady=8, sticky=tk.E)
        self.compare_end = ttk.Entry(ctrl_frame, width=12, font=("Microsoft YaHei", 10))
        self.compare_end.grid(row=0, column=5, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="开始对比", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_compare)
        btn.grid(row=0, column=6, padx=10, pady=8)

        chart_btn = tk.Button(ctrl_frame, text="生成对比图", font=("Microsoft YaHei", 10), bg="#8e44ad", fg="#fff",
                              activebackground="#6c3483", cursor="hand2", bd=0, padx=10, pady=5, command=self._do_compare_chart)
        chart_btn.grid(row=0, column=7, padx=5, pady=8)

        self._create_page_progress(page, "compare")

        self.compare_tree = self._create_dataframe_viewer(page)

    def _do_compare(self):
        def compare():
            codes_str = self.compare_codes.get().strip()
            codes = [c.strip() for c in re.split(r'[,，、;\s]+', codes_str) if c.strip()]
            self._set_status(f"已解析 {len(codes)} 只基金: {', '.join(codes[:5])}{'...' if len(codes) > 5 else ''}")
            if len(codes) < 2:
                return "too_few"
            start = self.compare_start.get().strip()
            end = self.compare_end.get().strip()
            df = analyzer.compare_funds(codes, start, end)
            _session["compare"] = df
            return df

        def on_done(df):
            if isinstance(df, str) and df == "too_few":
                self._show_error("至少需要 2 只基金")
                return
            if df is None or df.empty:
                self._show_error("基金对比失败，请检查基金代码是否正确")
                return
            self._display_dataframe(df, self.compare_tree)
            self._show_info("基金对比完成")

        self._run_async(compare, callback=on_done, page_key="compare")

    def _do_compare_chart(self):
        df = _session.get("compare")
        if df is None or df.empty:
            self._show_error("请先进行对比分析")
            return
        path = os.path.join(CHARTS_DIR, "return_comparison.html")
        try:
            visualizer.plot_return_comparison(df, path)
            self._set_status(f"对比图已生成: {path}")
            webbrowser.open(Path(path).as_uri())
        except Exception as e:
            self._show_error(f"生成图表失败: {e}")

    # ==================== 页面 7: 相关性分析 ====================

    def _build_correlation_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["correlation"] = page

        tk.Label(page, text="基金相关性分析", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="分析参数", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(ctrl_frame, text="基金代码(逗号分隔):", font=("Microsoft YaHei", 10)).grid(row=0, column=0, padx=5, pady=8, sticky=tk.E)
        self.corr_codes = ttk.Entry(ctrl_frame, width=40, font=("Microsoft YaHei", 10))
        self.corr_codes.insert(0, "000001,110022,161725")
        self.corr_codes.grid(row=0, column=1, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="开始分析", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_correlation)
        btn.grid(row=0, column=2, padx=10, pady=8)

        chart_btn = tk.Button(ctrl_frame, text="生成热力图", font=("Microsoft YaHei", 10), bg="#8e44ad", fg="#fff",
                              activebackground="#6c3483", cursor="hand2", bd=0, padx=10, pady=5, command=self._do_corr_chart)
        chart_btn.grid(row=0, column=3, padx=5, pady=8)

        self._create_page_progress(page, "correlation")

        self.corr_tree = self._create_dataframe_viewer(page)

    def _do_correlation(self):
        def corr():
            codes_str = self.corr_codes.get().strip()
            codes = [c.strip() for c in re.split(r'[,，、;\s]+', codes_str) if c.strip()]
            self._set_status(f"已解析 {len(codes)} 只基金: {', '.join(codes[:5])}{'...' if len(codes) > 5 else ''}")
            if len(codes) < 2:
                return "too_few"
            df = analyzer.correlation_analysis(codes)
            _session["correlation"] = df
            return df

        def on_done(df):
            if isinstance(df, str) and df == "too_few":
                self._show_error("至少需要 2 只基金")
                return
            if df is None or df.empty:
                self._show_error("相关性分析失败")
                return
            self._display_dataframe(df, self.corr_tree)
            self._set_status("相关性分析完成")

        self._run_async(corr, callback=on_done, page_key="correlation")

    def _do_corr_chart(self):
        df = _session.get("correlation")
        if df is None or df.empty:
            self._show_error("请先进行相关性分析")
            return
        path = os.path.join(CHARTS_DIR, "correlation_heatmap.html")
        try:
            visualizer.plot_correlation_heatmap(df, path)
            self._set_status(f"热力图已生成: {path}")
            webbrowser.open(Path(path).as_uri())
        except Exception as e:
            self._show_error(f"生成图表失败: {e}")

    # ==================== 页面 8: 可视化图表 ====================

    def _build_visualize_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["visualize"] = page

        tk.Label(page, text="生成可视化图表", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="图表类型", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        self.viz_type = ttk.Combobox(ctrl_frame, values=[
            "净值走势图", "收益对比图", "类型分布饼图", "相关性热力图", "增长率分布图"
        ], width=20, font=("Microsoft YaHei", 10))
        self.viz_type.set("净值走势图")
        self.viz_type.grid(row=0, column=0, padx=5, pady=8)

        ttk.Label(ctrl_frame, text="基金代码(可选):", font=("Microsoft YaHei", 10)).grid(row=0, column=1, padx=5, pady=8, sticky=tk.E)
        self.viz_code = ttk.Entry(ctrl_frame, width=15, font=("Microsoft YaHei", 10))
        self.viz_code.grid(row=0, column=2, padx=5, pady=8)

        btn = tk.Button(ctrl_frame, text="生成图表", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_visualize)
        btn.grid(row=0, column=3, padx=10, pady=8)

        open_btn = tk.Button(ctrl_frame, text="打开图表目录", font=("Microsoft YaHei", 10), bg="#27ae60", fg="#fff",
                             activebackground="#1e8449", cursor="hand2", bd=0, padx=10, pady=5, command=lambda: self._open_dir(CHARTS_DIR))
        open_btn.grid(row=0, column=4, padx=5, pady=8)

        self._create_page_progress(page, "visualize")

    def _do_visualize(self):
        self._start_progress("visualize")
        chart_type = self.viz_type.get()
        code = self.viz_code.get().strip()

        try:
            if chart_type == "净值走势图":
                if not code or code not in _session["history"]:
                    self._stop_progress("visualize", success=False)
                    self._show_error("请输入已分析过的基金代码")
                    return
                path = os.path.join(CHARTS_DIR, f"net_value_{code}.html")
                visualizer.plot_net_value_trend(code, _session["history"][code], path)
                self._open_chart(path)

            elif chart_type == "收益对比图":
                df = _session.get("compare")
                if df is None or df.empty:
                    self._stop_progress("visualize", success=False)
                    self._show_error("请先进行对比分析")
                    return
                path = os.path.join(CHARTS_DIR, "return_comparison.html")
                visualizer.plot_return_comparison(df, path)
                self._open_chart(path)

            elif chart_type == "类型分布饼图":
                # 安全获取数据源（修复 DataFrame 布尔值问题）
                df = _safe_get_df("fund_list", "ranking")
                if df is None:
                    self._stop_progress("visualize", success=False)
                    self._show_error("请先获取基金列表或排行数据")
                    return
                dist = analyzer.fund_type_distribution(df)
                path = os.path.join(CHARTS_DIR, "type_distribution.html")
                visualizer.plot_type_distribution(dist, path)
                self._open_chart(path)

            elif chart_type == "相关性热力图":
                df = _session.get("correlation")
                if df is None or df.empty:
                    self._stop_progress("visualize", success=False)
                    self._show_error("请先进行相关性分析")
                    return
                path = os.path.join(CHARTS_DIR, "correlation_heatmap.html")
                visualizer.plot_correlation_heatmap(df, path)
                self._open_chart(path)

            elif chart_type == "增长率分布图":
                if not code or code not in _session["history"]:
                    self._stop_progress("visualize", success=False)
                    self._show_error("请输入已分析过的基金代码")
                    return
                path = os.path.join(CHARTS_DIR, f"growth_distribution_{code}.html")
                visualizer.plot_growth_distribution(_session["history"][code], path)
                self._open_chart(path)

            self._set_status(f"图表已生成: {path}")
            self._set_progress("visualize", 100)
        except Exception as e:
            self._stop_progress("visualize", success=False)
            self._show_error(f"生成图表失败: {e}")

    def _open_chart(self, path):
        webbrowser.open(Path(path).as_uri())

    # ==================== 页面 9: 导出 Excel ====================

    def _build_export_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["export"] = page

        tk.Label(page, text="导出 Excel 报告", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)

        ctrl_frame = ttk.LabelFrame(page, text="导出选项", style="Panel.TLabelframe")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=5)

        self.export_vars = {}
        options = [
            ("fund_list", "基金列表"),
            ("ranking", "基金排行"),
            ("filtered", "筛选结果"),
            ("compare", "基金对比"),
            ("correlation", "相关性矩阵"),
        ]

        for i, (key, label) in enumerate(options):
            var = tk.BooleanVar(value=False)
            self.export_vars[key] = var
            chk = tk.Checkbutton(ctrl_frame, text=label, variable=var, font=("Microsoft YaHei", 10), bg="#fff",
                                 activebackground="#fff", selectcolor="#2c5aa0")
            chk.grid(row=0, column=i, padx=15, pady=8)

        btn = tk.Button(ctrl_frame, text="导出选中项", font=("Microsoft YaHei", 10, "bold"), bg="#2c5aa0", fg="#fff",
                        activebackground="#1a3a6e", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_export)
        btn.grid(row=0, column=len(options), padx=10, pady=8)

        all_btn = tk.Button(ctrl_frame, text="导出全部（多Sheet）", font=("Microsoft YaHei", 10, "bold"), bg="#27ae60", fg="#fff",
                            activebackground="#1e8449", cursor="hand2", bd=0, padx=15, pady=5, command=self._do_export_all)
        all_btn.grid(row=0, column=len(options)+1, padx=10, pady=8)

        self._create_page_progress(page, "export")

    def _do_export(self):
        self._start_progress("export")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exported = []
            for key, var in self.export_vars.items():
                if var.get():
                    df = _session.get(key)
                    if df is not None and not df.empty:
                        path = os.path.join(DATA_DIR, f"{key}_{timestamp}.xlsx")
                        with pd.ExcelWriter(path, engine="openpyxl") as writer:
                            df.to_excel(writer, sheet_name=key, index=(key in ("correlation", "compare")))
                        exported.append(key)
            if exported:
                self._show_info(f"已导出: {', '.join(exported)}")
            else:
                self._show_info("没有选中可导出的数据")
            self._set_progress("export", 100)
        except Exception as e:
            self._stop_progress("export", success=False)
            self._show_error(f"导出失败: {e}")

    def _do_export_all(self):
        self._start_progress("export")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(DATA_DIR, f"full_report_{timestamp}.xlsx")
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                sheet_count = 0
                if _session["fund_list"] is not None and not _session["fund_list"].empty:
                    _session["fund_list"].to_excel(writer, sheet_name="基金列表", index=False)
                    sheet_count += 1
                if _session["ranking"] is not None and not _session["ranking"].empty:
                    _session["ranking"].to_excel(writer, sheet_name="基金排行", index=False)
                    sheet_count += 1
                if _session["filtered"] is not None and not _session["filtered"].empty:
                    _session["filtered"].to_excel(writer, sheet_name="筛选结果", index=False)
                    sheet_count += 1
                if _session["compare"] is not None and not _session["compare"].empty:
                    _session["compare"].to_excel(writer, sheet_name="基金对比", index=True)
                    sheet_count += 1
                if _session["correlation"] is not None and not _session["correlation"].empty:
                    _session["correlation"].to_excel(writer, sheet_name="相关性矩阵", index=True)
                    sheet_count += 1

            self._set_status(f"综合报告已导出 ({sheet_count} 个 sheet)")
            self._show_info(f"已导出到 {path}")
            self._set_progress("export", 100)
        except Exception as e:
            self._stop_progress("export", success=False)
            self._show_error(f"导出失败: {e}")

    # ==================== 页面 10: 一键综合分析 ====================

    def _build_full_page(self):
        page = tk.Frame(self.content_frame, bg="#fff")
        self.pages["full"] = page

        tk.Label(page, text="一键综合分析", font=("Microsoft YaHei", 18, "bold"), bg="#fff", fg="#2c3e50").pack(pady=15)
        tk.Label(page, text="自动执行完整流程：爬取TOP20 → 逐只分析 → 导出Excel → 生成全部图表",
                 font=("Microsoft YaHei", 10), bg="#fff", fg="#7f8c8d").pack()

        ctrl_frame = tk.Frame(page, bg="#fff")
        ctrl_frame.pack(pady=20)

        self.full_btn = tk.Button(ctrl_frame, text="开始一键综合分析", font=("Microsoft YaHei", 12, "bold"), bg="#e74c3c", fg="#fff",
                                  activebackground="#c0392b", cursor="hand2", bd=0, padx=25, pady=10, command=self._do_full)
        self.full_btn.pack(pady=10)

        self.progress = ttk.Progressbar(page, mode="indeterminate", length=500)
        self.progress.pack(pady=10)

        log_frame = tk.Frame(page, bg="#fff")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        self.log_text = tk.Text(log_frame, height=20, wrap=tk.WORD, font=("Consolas", 10), bg="#fafafa", relief=tk.SUNKEN, bd=1)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.configure(yscrollcommand=scroll.set)

    def _do_full(self):
        def run_full():
            if not CORE_MODULES_LOADED:
                return "no_modules"

            self.root.after(0, lambda: self.progress.start())
            self.root.after(0, lambda: self._log_clear())
            self._append_log("=" * 50)
            self._append_log("开始一键综合分析...")
            self._append_log("=" * 50)

            # 1. 爬取排行
            self._append_log("\n[1/4] 爬取基金排行 TOP20...")
            ranking_df = crawler.get_fund_ranking(top_n=20)
            if ranking_df is None or ranking_df.empty:
                return "ranking_failed"
            _session["ranking"] = ranking_df
            self._append_log(f"  [OK] 成功获取 {len(ranking_df)} 条排行数据")
            ranking_path = os.path.join(DATA_DIR, "funds_ranking.csv")
            ranking_df.to_csv(ranking_path, index=False, encoding="utf-8-sig")

            # 2. 逐只分析
            self._append_log("\n[2/4] 逐只分析基金...")
            fund_codes = []
            for col in ["基金代码", "fund_code", "代码"]:
                if col in ranking_df.columns:
                    fund_codes = ranking_df[col].astype(str).tolist()
                    break
            if not fund_codes:
                fund_codes = [str(idx) for idx in ranking_df.index[:20]]

            analysis_results = []
            history_map = {}

            for i, code in enumerate(fund_codes[:20]):
                self._append_log(f"  [{i+1:2d}/20] 分析 {code}...")
                try:
                    df_his = crawler.get_fund_history(fund_code=code)
                    if df_his is not None and not df_his.empty:
                        history_map[code] = df_his
                        stats = analyzer.calculate_returns(df_his)
                        if stats:
                            stats["基金代码"] = code
                            name = ""
                            for col in ["基金简称", "基金名称"]:
                                if col in ranking_df.columns:
                                    try:
                                        name = ranking_df[ranking_df.iloc[:, 0].astype(str) == code][col].values
                                        if len(name) > 0:
                                            name = str(name[0])
                                            break
                                    except:
                                        pass
                            stats["基金名称"] = name
                            analysis_results.append(stats)
                            self._append_log(f"    [OK] {code}")
                except Exception as e:
                    self._append_log(f"    [FAIL] {code}: {str(e)[:40]}")

            _session["history"].update(history_map)
            self._append_log(f"  [OK] 完成 {len(analysis_results)} 只基金的分析")

            # 3. 导出 Excel
            self._append_log("\n[3/4] 导出 Excel 报告...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(DATA_DIR, f"full_analysis_{timestamp}.xlsx")

            dist_df = None
            try:
                with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
                    ranking_df.to_excel(writer, sheet_name="排行数据", index=False)
                    if analysis_results:
                        stats_df = pd.DataFrame(analysis_results)
                        stats_df.to_excel(writer, sheet_name="收益统计", index=False)
                    dist_df = analyzer.fund_type_distribution(ranking_df)
                    if dist_df is not None and not dist_df.empty:
                        dist_df.to_excel(writer, sheet_name="类型分布", index=False)
                self._append_log(f"  [OK] Excel 导出: {report_path}")
            except Exception as e:
                self._append_log(f"  [FAIL] Excel 导出失败: {e}")

            # 4. 生成图表
            self._append_log("\n[4/4] 生成可视化图表...")
            codes_with_data = list(history_map.keys())[:10]

            if dist_df is not None and not dist_df.empty:
                try:
                    visualizer.plot_type_distribution(dist_df, os.path.join(CHARTS_DIR, "type_distribution.html"))
                    self._append_log("  [OK] 类型分布饼图")
                except Exception as e:
                    self._append_log(f"  [FAIL] 类型分布图: {e}")

            if len(codes_with_data) >= 2:
                try:
                    corr_df = analyzer.correlation_analysis(codes_with_data)
                    if corr_df is not None and not corr_df.empty:
                        _session["correlation"] = corr_df
                        visualizer.plot_correlation_heatmap(corr_df, os.path.join(CHARTS_DIR, "correlation_heatmap.html"))
                        self._append_log("  [OK] 相关性热力图")
                except Exception as e:
                    self._append_log(f"  [FAIL] 相关性分析: {e}")

            for code in codes_with_data[:5]:
                try:
                    visualizer.plot_net_value_trend(code, history_map[code], os.path.join(CHARTS_DIR, f"net_value_{code}.html"))
                except:
                    pass
            self._append_log("  [OK] 净值走势图 (前5只)")

            for code in codes_with_data[:3]:
                try:
                    visualizer.plot_growth_distribution(history_map[code], os.path.join(CHARTS_DIR, f"growth_{code}.html"))
                except:
                    pass
            self._append_log("  [OK] 增长率分布图 (前3只)")

            self._append_log("\n" + "=" * 50)
            self._append_log("一键综合分析全部完成！")
            self._append_log(f"Excel 报告: {report_path}")
            self._append_log(f"图表目录: {os.path.abspath(CHARTS_DIR)}")
            self._append_log("=" * 50)
            return "done"

        def on_done(result):
            self.progress.stop()
            if result == "no_modules":
                self._show_error("核心模块未加载")
            elif result == "ranking_failed":
                self._show_error("爬取排行失败，终止分析")
            else:
                self._set_status("一键综合分析完成")
                self._show_info("分析完成！请查看 data 和 charts 目录")

        self._run_async(run_full, callback=on_done)

    def _append_log(self, msg):
        """线程安全的日志追加，使用 after 确保在主线程执行。"""
        self.root.after(0, lambda m=msg: self._do_append_log(m))

    def _do_append_log(self, msg):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self._set_status(msg)

    def _log_clear(self):
        self.log_text.delete(1.0, tk.END)


# ============================================================
# 主入口
# ============================================================
def main():
    root = tk.Tk()
    app = FundAnalyzerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
