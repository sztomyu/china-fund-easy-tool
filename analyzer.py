"""
基金数据分析模块

提供基金筛选、收益率计算、对比分析、相关性分析和类型分布统计等功能。
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _parse_percent(value):
    """
    解析百分比字符串为浮点数。

    支持格式: '12.34%' → 12.34, '--' → NaN, None → NaN, 纯数字 → float
    """
    if pd.isna(value) or value == '--' or value == '' or value is None:
        return np.nan
    if isinstance(value, str) and '%' in value:
        try:
            return float(value.replace('%', ''))
        except (ValueError, TypeError):
            return np.nan
    try:
        return float(value)
    except (ValueError, TypeError):
        return np.nan


def _find_column(df, candidates):
    """
    在 DataFrame 中根据候选列名列表查找实际存在的列。

    参数:
        df: DataFrame
        candidates: 候选列名列表
    返回:
        实际存在的列名，没找到返回 None
    """
    for col in candidates:
        if col in df.columns:
            return col
    return None


# ---------------------------------------------------------------------------
# 1. 基金筛选
# ---------------------------------------------------------------------------

def filter_funds(
    df,
    fund_type=None,
    min_return_1y=None,
    max_drawdown=None,
    min_rating=None,
    top_n=20
):
    """
    多维度条件筛选基金。

    链式过滤逻辑:
        基金类型 → 最低近1年收益率 → 最大回撤 → 最低评级 → 取 TopN

    参数:
        df: 基金排行 DataFrame（含 基金代码, 基金简称, 基金类型, 近1年 等列）
        fund_type: 基金类型过滤，str 或 list，如 ['股票型', '混合型']
        min_return_1y: 近1年最低收益率(%)，如 20.0
        max_drawdown: 最大回撤限制(%)，如 -30.0（可选，当前仅保留参数接口）
        min_rating: 最低星级 1-5（可选，当前仅保留参数接口）
        top_n: 返回前 N 个，默认 20

    返回:
        筛选后的 DataFrame，按近1年收益率降序排列
    """
    if df is None or df.empty:
        return pd.DataFrame()

    result = df.copy()

    # 1. 基金类型过滤
    if fund_type is not None:
        type_col = _find_column(result, ['基金类型', '类型', 'fund_type'])
        if type_col is not None:
            if isinstance(fund_type, str):
                result = result[result[type_col].astype(str).str.contains(fund_type, na=False)]
            elif isinstance(fund_type, (list, tuple)):
                result = result[result[type_col].isin(fund_type)]

    # 2. 最低近1年收益率过滤
    if min_return_1y is not None:
        return_col = _find_column(
            result,
            ['近1年', '近1年收益率', '1年收益率', '近1年收益', '年化收益率', '1nzf']
        )
        if return_col is not None:
            # 先解析百分比格式
            result[return_col] = result[return_col].apply(_parse_percent)
            result = result[result[return_col] >= min_return_1y]

    # 3. 最大回撤限制（保留参数接口，如数据列存在则过滤）
    if max_drawdown is not None:
        dd_col = _find_column(
            result,
            ['最大回撤', 'max_drawdown', '回撤']
        )
        if dd_col is not None:
            result[dd_col] = result[dd_col].apply(_parse_percent)
            result = result[result[dd_col] >= max_drawdown]

    # 4. 最低星级（保留参数接口，如数据列存在则过滤）
    if min_rating is not None:
        rating_col = _find_column(
            result,
            ['评级', '星级', 'rating', '基金评级']
        )
        if rating_col is not None:
            result[rating_col] = pd.to_numeric(result[rating_col], errors='coerce')
            result = result[result[rating_col] >= min_rating]

    # 5. 按近1年收益率降序排列，取 TopN
    sort_col = _find_column(
        result,
        ['近1年', '近1年收益率', '1年收益率', '近1年收益', '1nzf']
    )
    if sort_col is not None:
        # 确保排序列为数值类型
        if not pd.api.types.is_numeric_dtype(result[sort_col]):
            result[sort_col] = result[sort_col].apply(_parse_percent)
        result = result.sort_values(by=sort_col, ascending=False, na_position='last')

    # 取前 top_n 条
    if top_n is not None and top_n > 0:
        result = result.head(top_n)

    return result.reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. 收益率统计计算
# ---------------------------------------------------------------------------

def calculate_returns(df_history):
    """
    计算基金历史净值的核心收益指标。

    输入 DataFrame 列:
        净值日期, 单位净值, 累计净值, 日增长率

    计算指标:
        - 总收益率(%)
        - 年化收益率(%)
        - 波动率(%)
        - 夏普比率(简化)
        - 最大回撤(%)
        - 正增长天数
        - 负增长天数

    参数:
        df_history: 基金历史净值 DataFrame

    返回:
        dict: 各项收益指标
    """
    result = {
        'total_return': np.nan,
        'annualized_return': np.nan,
        'volatility': np.nan,
        'sharpe_ratio': np.nan,
        'max_drawdown': np.nan,
        'positive_days': 0,
        'negative_days': 0,
    }

    if df_history is None or df_history.empty:
        return result

    df = df_history.copy()

    # ---- 列名适配 ----
    nav_col = _find_column(df, ['单位净值', 'nav', 'NAV'])
    growth_col = _find_column(df, ['日增长率', 'daily_growth', '增长率', '日增长'])
    date_col = _find_column(df, ['净值日期', 'date', '日期', 'FSRQ'])

    if nav_col is None:
        return result

    # ---- 单位净值数值化 ----
    df[nav_col] = pd.to_numeric(df[nav_col], errors='coerce')
    nav_clean = df[nav_col].dropna()

    if nav_clean.empty or len(nav_clean) < 2:
        return result

    earliest_nav = nav_clean.iloc[-1]   # 最早净值（时间序列通常是倒序）
    latest_nav = nav_clean.iloc[0]      # 最新净值

    # 如果数据是正序排列的，取第一个和最后一个
    if earliest_nav > latest_nav and len(nav_clean) > 1:
        earliest_nav = nav_clean.iloc[0]
        latest_nav = nav_clean.iloc[-1]

    if earliest_nav <= 0 or np.isnan(earliest_nav) or np.isnan(latest_nav):
        return result

    # ---- 总收益率 ----
    total_return = (latest_nav - earliest_nav) / earliest_nav * 100.0
    result['total_return'] = total_return

    # ---- 年化收益率 ----
    if date_col is not None:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        valid_dates = df[date_col].dropna()
        if len(valid_dates) >= 2:
            # 计算实际交易天数
            day_count = (valid_dates.max() - valid_dates.min()).days
            if day_count <= 0:
                day_count = len(valid_dates)
        else:
            day_count = len(df)
    else:
        day_count = len(df)

    if day_count > 0:
        annualized_return = (
            (1.0 + total_return / 100.0) ** (365.0 / day_count) - 1.0
        ) * 100.0
        result['annualized_return'] = annualized_return
    else:
        annualized_return = np.nan
        result['annualized_return'] = np.nan

    # ---- 日增长率处理 ----
    if growth_col is not None:
        df[growth_col] = df[growth_col].apply(_parse_percent)
        growth_clean = df[growth_col].dropna()
    else:
        # 用单位净值计算日增长率（单位净值应为正序或倒序对应正确）
        nav_sorted = df[nav_col].dropna().sort_index(ascending=True)
        if len(nav_sorted) >= 2:
            daily_returns = nav_sorted.pct_change().dropna() * 100.0
            growth_clean = daily_returns
        else:
            growth_clean = pd.Series(dtype=float)

    # ---- 波动率 = 日增长率标准差 × √252 ----
    if not growth_clean.empty:
        volatility = growth_clean.std() * np.sqrt(252)
        result['volatility'] = volatility

        # ---- 夏普比率（简化版: 年化收益率 / 波动率）----
        if volatility > 1e-10 and not np.isnan(annualized_return):
            result['sharpe_ratio'] = annualized_return / volatility
        else:
            result['sharpe_ratio'] = np.nan

        # ---- 正/负增长天数统计 ----
        result['positive_days'] = int((growth_clean > 0).sum())
        result['negative_days'] = int((growth_clean < 0).sum())
    else:
        result['volatility'] = np.nan
        result['sharpe_ratio'] = np.nan

    # ---- 最大回撤 ----
    nav_series = df[nav_col].dropna().values
    if len(nav_series) >= 2:
        # 计算滚动峰值，然后计算回撤
        cumulative_max = np.maximum.accumulate(nav_series)
        drawdowns = (nav_series - cumulative_max) / cumulative_max * 100.0
        # 最大回撤是回撤中最小的值（最大的跌幅）
        max_drawdown = drawdowns.min()
        result['max_drawdown'] = max_drawdown
    else:
        result['max_drawdown'] = np.nan

    return result


# ---------------------------------------------------------------------------
# 3. 基金对比分析
# ---------------------------------------------------------------------------

def compare_funds(fund_codes, start_date="", end_date=""):
    """
    对比多只基金在同一时期的表现。

    参数:
        fund_codes: 基金代码列表，如 ['000001', '110011']
        start_date: 起始日期 YYYY-MM-DD，空字符串表示最早
        end_date: 结束日期 YYYY-MM-DD，空字符串表示最新

    返回:
        DataFrame，列:
            基金代码, 总收益率, 年化收益率, 波动率,
            最大回撤, 夏普比率, 正增长天数, 负增长天数
        按总收益率降序排列。
        如果爬虫模块导入失败或 fund_codes 为空，返回空 DataFrame。
    """
    # 定义标准列名
    columns = [
        '基金代码', '总收益率', '年化收益率', '波动率',
        '最大回撤', '夏普比率', '正增长天数', '负增长天数'
    ]

    if not fund_codes:
        return pd.DataFrame(columns=columns)

    # 动态导入爬虫模块
    try:
        from core.crawler import get_fund_history
    except ImportError:
        try:
            from fund_analyzer.core.crawler import get_fund_history
        except ImportError:
            return pd.DataFrame(columns=columns)

    rows = []
    for code in fund_codes:
        try:
            # 获取基金历史数据
            history_df = get_fund_history(code, start_date=start_date, end_date=end_date)

            if history_df is None or history_df.empty:
                continue

            # 计算收益率指标
            metrics = calculate_returns(history_df)

            row = {
                '基金代码': code,
                '总收益率': metrics['total_return'],
                '年化收益率': metrics['annualized_return'],
                '波动率': metrics['volatility'],
                '最大回撤': metrics['max_drawdown'],
                '夏普比率': metrics['sharpe_ratio'],
                '正增长天数': metrics['positive_days'],
                '负增长天数': metrics['negative_days'],
            }
            rows.append(row)
        except Exception:
            # 单只基金异常不影响其他基金
            continue

    if not rows:
        return pd.DataFrame(columns=columns)

    compare_df = pd.DataFrame(rows)

    # 按总收益率降序排列
    compare_df = compare_df.sort_values(
        by='总收益率', ascending=False, na_position='last'
    ).reset_index(drop=True)

    return compare_df


# ---------------------------------------------------------------------------
# 4. 基金相关性分析
# ---------------------------------------------------------------------------

def correlation_analysis(fund_codes):
    """
    计算多只基金日增长率的相关性矩阵。

    参数:
        fund_codes: 基金代码列表，如 ['000001', '110011', '005827']

    返回:
        DataFrame: 相关性矩阵，索引和列均为基金代码
        如果基金少于 2 只、数据不足或爬虫导入失败，返回空 DataFrame。
    """
    if not fund_codes or len(fund_codes) < 2:
        return pd.DataFrame()

    # 动态导入爬虫模块
    try:
        from core.crawler import get_fund_history
    except ImportError:
        try:
            from fund_analyzer.core.crawler import get_fund_history
        except ImportError:
            return pd.DataFrame()

    # 收集每只基金的日增长率序列
    growth_dict = {}

    for code in fund_codes:
        try:
            history_df = get_fund_history(code)

            if history_df is None or history_df.empty:
                continue

            # 查找日期列和日增长率列
            date_col = _find_column(
                history_df,
                ['净值日期', 'date', '日期', 'FSRQ']
            )
            growth_col = _find_column(
                history_df,
                ['日增长率', 'daily_growth', '增长率', '日增长']
            )

            if growth_col is None or date_col is None:
                # 尝试用单位净值计算日增长率
                nav_col = _find_column(history_df, ['单位净值', 'nav', 'NAV'])
                if nav_col is not None and date_col is not None:
                    df_tmp = history_df[[date_col, nav_col]].copy()
                    df_tmp[date_col] = pd.to_datetime(df_tmp[date_col], errors='coerce')
                    df_tmp[nav_col] = pd.to_numeric(df_tmp[nav_col], errors='coerce')
                    df_tmp = df_tmp.dropna()
                    df_tmp = df_tmp.sort_values(by=date_col)
                    if len(df_tmp) >= 2:
                        df_tmp['growth'] = df_tmp[nav_col].pct_change() * 100.0
                        df_tmp = df_tmp.dropna()
                        df_tmp = df_tmp.set_index(date_col)['growth']
                        growth_dict[code] = df_tmp
                continue

            # 解析日增长率
            df_tmp = history_df[[date_col, growth_col]].copy()
            df_tmp[date_col] = pd.to_datetime(df_tmp[date_col], errors='coerce')
            df_tmp[growth_col] = df_tmp[growth_col].apply(_parse_percent)
            df_tmp = df_tmp.dropna()

            if df_tmp.empty:
                continue

            df_tmp = df_tmp.set_index(date_col)[growth_col]
            growth_dict[code] = df_tmp

        except Exception:
            continue

    # 检查是否有至少 2 只基金的数据
    if len(growth_dict) < 2:
        return pd.DataFrame()

    # 按日期对齐，构建联合 DataFrame
    aligned_df = pd.DataFrame(growth_dict)

    if aligned_df.empty or aligned_df.shape[1] < 2:
        return pd.DataFrame()

    # 计算相关性矩阵
    corr_matrix = aligned_df.corr()

    return corr_matrix


# ---------------------------------------------------------------------------
# 5. 基金类型分布统计
# ---------------------------------------------------------------------------

def fund_type_distribution(df):
    """
    按基金类型统计分布。

    统计内容:
        - 各类基金数量
        - 各类基金平均收益率

    参数:
        df: 基金排行 DataFrame，需包含 '基金类型' 列和收益率相关列

    返回:
        DataFrame，列: 基金类型, 数量, 平均收益率
        如果缺少必要列，返回空 DataFrame。
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # 查找基金类型列
    type_col = _find_column(df, ['基金类型', '类型', 'fund_type'])
    if type_col is None:
        return pd.DataFrame()

    # 查找收益率列（优先使用近1年）
    return_col = _find_column(
        df,
        ['近1年', '近1年收益率', '1年收益率', '近1年收益', '1nzf']
    )

    # 复制并解析收益率
    df_copy = df.copy()
    if return_col is not None and not pd.api.types.is_numeric_dtype(df_copy[return_col]):
        df_copy[return_col] = df_copy[return_col].apply(_parse_percent)

    # 按基金类型分组
    grouped = df_copy.groupby(type_col)

    # 统计数量和平均收益率
    stats = grouped.size().reset_index(name='数量')

    if return_col is not None:
        avg_return = grouped[return_col].mean().reset_index(name='平均收益率')
        stats = stats.merge(avg_return, on=type_col)
    else:
        stats['平均收益率'] = np.nan

    # 重命名列
    stats = stats.rename(columns={type_col: '基金类型'})

    # 按数量降序排列
    stats = stats.sort_values(by='数量', ascending=False).reset_index(drop=True)

    return stats
