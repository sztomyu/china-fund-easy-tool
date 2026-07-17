"""
报告导出模块 - 将基金分析结果导出为 Excel 报告
使用 openpyxl 引擎，支持自动调整列宽和多 sheet 导出
"""

import pandas as pd
import os
from datetime import datetime


def _adjust_column_width(writer, df, sheet_name):
    """
    自动调整 Excel 列宽
    
    参数:
        writer: ExcelWriter 对象
        df: DataFrame
        sheet_name: 工作表名称
    """
    worksheet = writer.sheets[sheet_name]
    
    for idx, col in enumerate(df.columns):
        # 获取列的最大长度
        header_len = len(str(col))
        max_data_len = 0
        
        # 检查数据长度
        for val in df[col].astype(str):
            val_len = len(val)
            if val_len > max_data_len:
                max_data_len = val_len
        
        # 取标题和数据的最大值，设置列宽（加一些边距）
        max_length = max(header_len, max_data_len) + 2
        
        # 限制最大列宽为50
        if max_length > 50:
            max_length = 50
        
        # 设置列宽（openpyxl列索引从1开始）
        worksheet.column_dimensions[worksheet.cell(row=1, column=idx + 1).column_letter].width = max_length


def _ensure_dir(filepath):
    """
    确保文件所在目录存在
    
    参数:
        filepath: 文件路径
    """
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def export_fund_list(df, filepath):
    """
    导出基金列表到 Excel
    
    参数:
        df: 基金列表 DataFrame[基金代码, 基金名称, 基金类型, 拼音缩写]
        filepath: 导出文件路径
    """
    if df.empty:
        print("[警告] 基金列表为空，无法导出")
        return
    
    _ensure_dir(filepath)
    
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='基金列表', index=False)
            _adjust_column_width(writer, df, '基金列表')
        
        print(f"[成功] 基金列表已导出: {filepath}")
    except Exception as e:
        print(f"[错误] 导出基金列表失败: {e}")


def export_ranking_report(ranking_df, filepath):
    """
    导出基金排行报告
    
    参数:
        ranking_df: 排行数据 DataFrame
        filepath: 导出文件路径
    """
    if ranking_df.empty:
        print("[警告] 排行数据为空，无法导出")
        return
    
    _ensure_dir(filepath)
    
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            ranking_df.to_excel(writer, sheet_name='基金排行', index=False)
            _adjust_column_width(writer, ranking_df, '基金排行')
        
        print(f"[成功] 排行报告已导出: {filepath}")
    except Exception as e:
        print(f"[错误] 导出排行报告失败: {e}")


def export_comparison_report(compare_df, filepath):
    """
    导出基金对比报告
    
    参数:
        compare_df: 对比数据 DataFrame
        filepath: 导出文件路径
    """
    if compare_df.empty:
        print("[警告] 对比数据为空，无法导出")
        return
    
    _ensure_dir(filepath)
    
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            compare_df.to_excel(writer, sheet_name='基金对比', index=False)
            _adjust_column_width(writer, compare_df, '基金对比')
        
        print(f"[成功] 对比报告已导出: {filepath}")
    except Exception as e:
        print(f"[错误] 导出对比报告失败: {e}")


def generate_full_report(fund_code, history_df, analysis_result, output_dir):
    """
    为单只基金生成完整分析报告（多 sheet）
    
    参数:
        fund_code: 基金代码
        history_df: 历史净值 DataFrame[净值日期, 单位净值, 累计净值, 日增长率]
        analysis_result: 分析结果字典 {
            total_return: 总收益率(%),
            annualized_return: 年化收益率(%),
            volatility: 波动率(%),
            sharpe_ratio: 夏普比率,
            max_drawdown: 最大回撤(%),
            positive_days: 正增长天数,
            negative_days: 负增长天数
        }
        output_dir: 输出目录
    """
    if history_df.empty:
        print("[警告] 历史净值数据为空，无法生成报告")
        return
    
    _ensure_dir(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fund_report_{fund_code}_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Sheet1: 基本信息与收益统计
            info_data = {
                "指标": [
                    "基金代码",
                    "分析日期",
                    "数据区间",
                    "总收益率 (%)",
                    "年化收益率 (%)",
                    "波动率 (%)",
                    "夏普比率",
                    "最大回撤 (%)",
                    "正增长天数",
                    "负增长天数",
                    "总交易日数"
                ],
                "数值": [
                    fund_code,
                    datetime.now().strftime("%Y-%m-%d"),
                    f"{history_df['净值日期'].iloc[-1]} 至 {history_df['净值日期'].iloc[0]}",
                    analysis_result.get("total_return", "N/A"),
                    analysis_result.get("annualized_return", "N/A"),
                    analysis_result.get("volatility", "N/A"),
                    analysis_result.get("sharpe_ratio", "N/A"),
                    analysis_result.get("max_drawdown", "N/A"),
                    analysis_result.get("positive_days", "N/A"),
                    analysis_result.get("negative_days", "N/A"),
                    len(history_df)
                ]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, sheet_name='基本信息与收益统计', index=False)
            _adjust_column_width(writer, info_df, '基本信息与收益统计')
            
            # Sheet2: 历史净值
            history_df.to_excel(writer, sheet_name='历史净值', index=False)
            _adjust_column_width(writer, history_df, '历史净值')
            
            # Sheet3: 收益统计摘要
            summary_data = {
                "统计项": [
                    "最新净值",
                    "最早净值",
                    "净值最高点",
                    "净值最低点",
                    "平均日增长率 (%)",
                    "日增长率标准差",
                    "最佳单日涨幅 (%)",
                    "最差单日跌幅 (%)",
                    "正增长天数",
                    "负增长天数",
                    "持平天数"
                ],
                "数值": [
                    history_df['单位净值'].iloc[0] if len(history_df) > 0 else "N/A",
                    history_df['单位净值'].iloc[-1] if len(history_df) > 0 else "N/A",
                    history_df['单位净值'].max() if len(history_df) > 0 else "N/A",
                    history_df['单位净值'].min() if len(history_df) > 0 else "N/A",
                    _safe_calc(history_df, '日增长率', 'mean'),
                    _safe_calc(history_df, '日增长率', 'std'),
                    history_df['日增长率'].max() if len(history_df) > 0 else "N/A",
                    history_df['日增长率'].min() if len(history_df) > 0 else "N/A",
                    _count_positive_days(history_df),
                    _count_negative_days(history_df),
                    _count_flat_days(history_df)
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='收益统计摘要', index=False)
            _adjust_column_width(writer, summary_df, '收益统计摘要')
        
        print(f"[成功] 完整报告已生成: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"[错误] 生成完整报告失败: {e}")
        return None


def _safe_calc(df, column, operation):
    """
    安全地计算统计值
    
    参数:
        df: DataFrame
        column: 列名
        operation: 操作 (mean, std, sum 等)
    
    返回:
        计算结果或 "N/A"
    """
    try:
        if column not in df.columns or df.empty:
            return "N/A"
        
        # 将列转为数值类型，非数值转为NaN
        series = pd.to_numeric(df[column], errors='coerce').dropna()
        
        if series.empty:
            return "N/A"
        
        if operation == 'mean':
            return round(series.mean(), 4)
        elif operation == 'std':
            return round(series.std(), 4)
        elif operation == 'sum':
            return round(series.sum(), 4)
        elif operation == 'max':
            return round(series.max(), 4)
        elif operation == 'min':
            return round(series.min(), 4)
        else:
            return "N/A"
    except Exception:
        return "N/A"


def _count_positive_days(df):
    """统计正增长天数"""
    try:
        series = pd.to_numeric(df['日增长率'], errors='coerce').dropna()
        return int((series > 0).sum())
    except Exception:
        return "N/A"


def _count_negative_days(df):
    """统计负增长天数"""
    try:
        series = pd.to_numeric(df['日增长率'], errors='coerce').dropna()
        return int((series < 0).sum())
    except Exception:
        return "N/A"


def _count_flat_days(df):
    """统计持平天数"""
    try:
        series = pd.to_numeric(df['日增长率'], errors='coerce').dropna()
        return int((series == 0).sum())
    except Exception:
        return "N/A"


# 测试入口
if __name__ == "__main__":
    print("=" * 50)
    print("报告导出模块测试")
    print("=" * 50)
    
    # 创建测试数据
    test_fund_list = pd.DataFrame({
        "基金代码": ["000001", "000002", "000003"],
        "基金名称": ["华夏成长", "华夏大盘", "嘉实增长"],
        "基金类型": ["混合型", "股票型", "混合型"],
        "拼音缩写": ["HXCZ", "HXDP", "JSZZ"]
    })
    
    test_ranking = pd.DataFrame({
        "基金代码": ["000001", "000002"],
        "基金简称": ["华夏成长", "华夏大盘"],
        "日期": ["2024-01-01", "2024-01-01"],
        "单位净值": ["1.5000", "2.3000"],
        "累计净值": ["3.2000", "5.1000"],
        "日增长率": ["0.50%", "1.20%"],
        "近1周": ["1.50%", "2.30%"],
        "近1月": ["3.50%", "5.20%"],
        "近3月": ["8.50%", "12.30%"],
        "近6月": ["15.50%", "22.30%"],
        "近1年": ["25.50%", "35.20%"],
        "近2年": ["45.50%", "55.30%"],
        "近3年": ["65.50%", "78.20%"],
        "今年来": ["10.50%", "15.30%"],
        "成立来": ["220.50%", "380.20%"],
        "手续费": ["1.50%", "1.50%"]
    })
    
    test_history = pd.DataFrame({
        "净值日期": ["2024-01-03", "2024-01-02", "2024-01-01"],
        "单位净值": ["1.5200", "1.5150", "1.5100"],
        "累计净值": ["3.2200", "3.2150", "3.2100"],
        "日增长率": ["0.33", "0.33", "0.33"]
    })
    
    test_analysis = {
        "total_return": 15.5,
        "annualized_return": 12.3,
        "volatility": 18.5,
        "sharpe_ratio": 0.67,
        "max_drawdown": -12.5,
        "positive_days": 128,
        "negative_days": 97
    }
    
    output_dir = "/mnt/agents/output/fund_analyzer/data/test_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # 测试导出基金列表
    print("\n[测试1] 导出基金列表...")
    export_fund_list(test_fund_list, f"{output_dir}/fund_list.xlsx")
    
    # 测试导出排行报告
    print("\n[测试2] 导出排行报告...")
    export_ranking_report(test_ranking, f"{output_dir}/ranking_report.xlsx")
    
    # 测试导出对比报告
    print("\n[测试3] 导出对比报告...")
    export_comparison_report(test_ranking, f"{output_dir}/comparison_report.xlsx")
    
    # 测试生成完整报告
    print("\n[测试4] 生成完整报告...")
    generate_full_report("000001", test_history, test_analysis, output_dir)
    
    print("\n[完成] 所有测试完成")
