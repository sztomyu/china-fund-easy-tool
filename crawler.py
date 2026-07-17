"""
爬虫模块 - 从天天基金网(fund.eastmoney.com)爬取基金数据
"""

import requests
import pandas as pd
import re
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from tqdm import tqdm

# 请求头配置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/"
}

# 排行页面专用的Referer
RANKING_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/data/fundranking.html"
}


def _http_get_with_retry(url, params=None, headers=None, retries=3, delay=0.5):
    """
    带重试的HTTP GET请求
    
    参数:
        url: 请求URL
        params: URL参数
        headers: 自定义请求头
        retries: 最大重试次数
        delay: 重试间隔(秒)
    
    返回:
        响应文本内容，失败返回None
    """
    if headers is None:
        headers = HEADERS
    
    for i in range(retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.encoding = 'utf-8'
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            print(f"[警告] 请求失败 ({i+1}/{retries}): {url}, 错误: {e}")
            if i < retries - 1:
                time.sleep(delay)
    return None


def get_fund_list():
    """
    获取全部基金列表
    
    返回:
        DataFrame[基金代码, 基金名称, 基金类型, 拼音缩写]
    数据源:
        http://fund.eastmoney.com/js/fundcode_search.js
    """
    url = "http://fund.eastmoney.com/js/fundcode_search.js"
    text = _http_get_with_retry(url)
    
    if text is None:
        print("[错误] 获取基金列表失败")
        return pd.DataFrame(columns=["基金代码", "基金名称", "基金类型", "拼音缩写"])
    
    try:
        # 使用正则提取基金数据: "code","abbr","name","type","pinyin"
        pattern = r'"(\d*?)","(.*?)","(.*?)","(.*?)","(.*?)"'
        matches = re.findall(pattern, text)
        
        if not matches:
            print("[警告] 未匹配到基金数据")
            return pd.DataFrame(columns=["基金代码", "基金名称", "基金类型", "拼音缩写"])
        
        # 构建DataFrame
        df = pd.DataFrame(matches, columns=["基金代码", "拼音缩写", "基金名称", "基金类型", "拼音全拼"])
        df = df[["基金代码", "基金名称", "基金类型", "拼音缩写"]]
        
        print(f"[成功] 获取到 {len(df)} 只基金信息")
        return df
        
    except Exception as e:
        print(f"[错误] 解析基金列表失败: {e}")
        return pd.DataFrame(columns=["基金代码", "基金名称", "基金类型", "拼音缩写"])


def get_fund_ranking(fund_type="all", sort_by="1nzf", top_n=100, date_range="1y"):
    """
    获取基金排行数据（按收益率排序）
    
    参数:
        fund_type: 基金类型 (all/gp/zq/hh,zq,pg)
        sort_by: 排序字段 (1nzf=近1年, 3yzf=近3月, 6yzf=近6月, 1nzf=近1年)
        top_n: 获取前N条
        date_range: 时间范围 (1y/3y/5y)
    
    返回:
        DataFrame[基金代码, 基金简称, 日期, 单位净值, 累计净值, 日增长率,
                  近1周, 近1月, 近3月, 近6月, 近1年, 近2年, 近3年, 今年来, 成立来, 手续费]
    数据源:
        https://fund.eastmoney.com/data/rankhandler.aspx
    """
    # 计算日期范围
    end_date = datetime.now()
    if date_range == "1y":
        start_date = end_date - timedelta(days=365)
    elif date_range == "3y":
        start_date = end_date - timedelta(days=1095)
    elif date_range == "5y":
        start_date = end_date - timedelta(days=1825)
    else:
        start_date = end_date - timedelta(days=365)
    
    sd = start_date.strftime("%Y-%m-%d")
    ed = end_date.strftime("%Y-%m-%d")
    
    url = "https://fund.eastmoney.com/data/rankhandler.aspx"
    all_data = []
    
    # 计算需要爬取的页数
    pages_needed = (top_n + 49) // 50  # 每页50条，向上取整
    
    print(f"[信息] 开始获取基金排行数据，类型={fund_type}, 排序={sort_by}, 目标={top_n}条")
    
    for page in tqdm(range(1, pages_needed + 1), desc="爬取排行数据"):
        params = {
            "op": "ph",
            "dt": "kf",
            "ft": fund_type,
            "gs": "0",
            "sc": sort_by,
            "st": "desc",
            "sd": sd,
            "ed": ed,
            "pi": str(page),
            "pn": "50",
            "dx": "1"
        }
        
        text = _http_get_with_retry(url, params=params, headers=RANKING_HEADERS)
        if text is None:
            print(f"[警告] 第{page}页请求失败，跳过")
            continue
        
        try:
            # 提取 datas 数组 (JSONP格式)
            match = re.search(r'datas:\[(.*?)\]', text, re.DOTALL)
            if not match:
                continue
            
            # 解析数据列表
            datas_str = match.group(1)
            # 安全地解析字符串列表
            try:
                data_list = eval(f"[{datas_str}]")
            except Exception:
                # 备选解析方式
                data_list = re.findall(r'"([^"]*)"', datas_str)
            
            for item in data_list:
                parts = item.split(",")
                if len(parts) >= 15:
                    all_data.append(parts)
            
            # 检查是否已获取足够数据
            if len(all_data) >= top_n:
                break
                
            time.sleep(0.3)  # 请求间隔
            
        except Exception as e:
            print(f"[警告] 解析第{page}页数据失败: {e}")
            continue
    
    if not all_data:
        print("[错误] 未获取到任何排行数据")
        return pd.DataFrame(columns=["基金代码", "基金简称", "日期", "单位净值", "累计净值",
                                      "日增长率", "近1周", "近1月", "近3月", "近6月",
                                      "近1年", "近2年", "近3年", "今年来", "成立来", "手续费"])
    
    # 截取前top_n条
    all_data = all_data[:top_n]
    
    # 构建DataFrame - 天天基金API返回25个字段
    columns = ["基金代码", "基金简称", "拼音缩写", "日期", "单位净值", "累计净值", "日增长率",
               "近1周", "近1月", "近3月", "近6月", "近1年", "近2年", "近3年", "今年来", "成立来",
               "成立日期", "自定义字段1", "基金规模", "申购费率", "赎回费率",
               "自定义字段2", "手续费", "自定义字段3", "自定义字段4"]
    
    df = pd.DataFrame(all_data, columns=columns)
    print(f"[成功] 获取到 {len(df)} 条排行数据")
    return df


def get_fund_history(fund_code, start_date="", end_date="", per_page=49):
    """
    获取单只基金历史净值
    
    参数:
        fund_code: 基金代码
        start_date: 开始日期 (YYYY-MM-DD)，空表示最早
        end_date: 结束日期 (YYYY-MM-DD)，空表示最新
        per_page: 每页条数
    
    返回:
        DataFrame[净值日期, 单位净值, 累计净值, 日增长率]
    数据源:
        http://fund.eastmoney.com/f10/F10DataApi.aspx?type=lsjz
    """
    url = "http://fund.eastmoney.com/f10/F10DataApi.aspx"
    
    # 第一次请求获取总页数
    params = {
        "type": "lsjz",
        "code": fund_code,
        "page": "1",
        "per": str(per_page),
    }
    if start_date:
        params["sdate"] = start_date
    if end_date:
        params["edate"] = end_date
    
    text = _http_get_with_retry(url, params=params)
    if text is None:
        print(f"[错误] 获取基金 {fund_code} 历史净值失败")
        return pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])
    
    # 提取总页数
    pages_match = re.search(r'pages:(\d+)', text)
    if not pages_match:
        print(f"[警告] 无法获取总页数，基金代码: {fund_code}")
        return pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])
    
    total_pages = int(pages_match.group(1))
    print(f"[信息] 基金 {fund_code} 共有 {total_pages} 页历史数据")
    
    all_rows = []
    
    # 解析第一页数据
    first_page_data = _parse_history_page(text)
    all_rows.extend(first_page_data)
    
    # 循环获取剩余页面
    if total_pages > 1:
        for page in tqdm(range(2, total_pages + 1), desc=f"爬取{fund_code}历史净值"):
            params["page"] = str(page)
            text = _http_get_with_retry(url, params=params)
            if text is None:
                print(f"[警告] 第{page}页请求失败，跳过")
                continue
            
            page_data = _parse_history_page(text)
            all_rows.extend(page_data)
            time.sleep(0.3)  # 请求间隔
    
    if not all_rows:
        print(f"[警告] 基金 {fund_code} 未获取到历史数据")
        return pd.DataFrame(columns=["净值日期", "单位净值", "累计净值", "日增长率"])
    
    # 构建DataFrame
    df = pd.DataFrame(all_rows, columns=["净值日期", "单位净值", "累计净值", "日增长率"])
    print(f"[成功] 基金 {fund_code} 获取到 {len(df)} 条历史净值记录")
    return df


def _parse_history_page(text):
    """
    解析历史净值页面中的HTML表格数据
    
    参数:
        text: API返回的文本内容
    
    返回:
        list[dict]: 每条记录的列表
    """
    rows = []
    try:
        # 提取content部分 (JSONP格式: var apidata={ content:"...", records:... })
        content_match = re.search(r'content:"(.*?)"', text, re.DOTALL)
        if content_match:
            html_content = content_match.group(1)
            # 转义引号
            html_content = html_content.replace('\\"', '"')
        else:
            # 尝试直接提取HTML
            html_content = text
        
        soup = BeautifulSoup(html_content, 'html.parser')
        tbody = soup.find('tbody')
        if not tbody:
            return rows
        
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) >= 4:
                date = tds[0].get_text(strip=True)
                unit_value = tds[1].get_text(strip=True)
                accum_value = tds[2].get_text(strip=True)
                daily_growth = tds[3].get_text(strip=True)
                
                # 处理空值
                if daily_growth == '' or daily_growth == '--':
                    daily_growth = None
                
                rows.append({
                    "净值日期": date,
                    "单位净值": unit_value,
                    "累计净值": accum_value,
                    "日增长率": daily_growth
                })
    except Exception as e:
        print(f"[警告] 解析历史净值页面失败: {e}")
    
    return rows


def get_fund_detail(fund_code):
    """
    获取基金基本信息
    
    参数:
        fund_code: 基金代码
    
    返回:
        dict: {基金代码, 基金名称, 基金类型, 成立日期, 管理公司, 基金经理, 规模, 评级}
    """
    url = f"https://fund.eastmoney.com/f10/{fund_code}.html"
    text = _http_get_with_retry(url)
    
    if text is None:
        print(f"[错误] 获取基金 {fund_code} 详情失败")
        return {
            "基金代码": fund_code,
            "基金名称": "",
            "基金类型": "",
            "成立日期": "",
            "管理公司": "",
            "基金经理": "",
            "规模": "",
            "评级": ""
        }
    
    try:
        soup = BeautifulSoup(text, 'html.parser')
        
        # 初始化结果
        detail = {
            "基金代码": fund_code,
            "基金名称": "",
            "基金类型": "",
            "成立日期": "",
            "管理公司": "",
            "基金经理": "",
            "规模": "",
            "评级": ""
        }
        
        # 尝试多种选择器获取基金名称
        name_selectors = [
            '.fundDetail-tit', '.fund_name', '#body',
            'h1.tit', '.fund-info h1',
            'div.fundDetail-name'
        ]
        for selector in name_selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                detail["基金名称"] = name_elem.get_text(strip=True)
                break
        
        # 如果上面的选择器没找到，尝试从title中提取
        if not detail["基金名称"]:
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # 通常格式: "基金名称(代码)_基金详情..."
                name_match = re.search(r'(.+?)\(\d+\)', title_text)
                if name_match:
                    detail["基金名称"] = name_match.group(1).strip()
        
        # 从infoTips中提取信息
        info_tips = soup.find('div', class_='infoTips')
        if info_tips:
            tips_text = info_tips.get_text(strip=True)
            # 提取成立日期
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', tips_text)
            if date_match:
                detail["成立日期"] = date_match.group(1)
        
        # 查找表格数据 (基金档案表格)
        tables = soup.find_all('table')
        for table in tables:
            # 遍历表格中的行查找关键信息
            rows = table.find_all('tr')
            for tr in rows:
                th = tr.find('th')
                td = tr.find('td')
                if th and td:
                    th_text = th.get_text(strip=True)
                    td_text = td.get_text(strip=True)
                    
                    if '基金类型' in th_text or '类型' in th_text:
                        detail["基金类型"] = td_text
                    elif '成立日期' in th_text or '成立日' in th_text:
                        detail["成立日期"] = td_text
                    elif '基金公司' in th_text or '管理人' in th_text or '管理公司' in th_text:
                        detail["管理公司"] = td_text
                    elif '基金经理' in th_text or '经理人' in th_text:
                        detail["基金经理"] = td_text
                    elif '资产规模' in th_text or '规模' in th_text:
                        detail["规模"] = td_text
                    elif '评级' in th_text:
                        # 提取星级
                        stars = td.find_all('div', class_='star')
                        if stars:
                            detail["评级"] = f"{len(stars)}星"
                        else:
                            star_text = td_text
                            if '星' in star_text:
                                detail["评级"] = star_text
        
        # 如果表格方式没找到，尝试用正则匹配
        if not detail["基金类型"]:
            type_match = re.search(r'基金类型[：:]\s*([^<\n]+)', text)
            if type_match:
                detail["基金类型"] = type_match.group(1).strip()
        
        if not detail["管理公司"]:
            company_match = re.search(r'基金管理人[：:]\s*([^<\n]+)', text)
            if company_match:
                detail["管理公司"] = company_match.group(1).strip()
        
        if not detail["基金经理"]:
            manager_match = re.search(r'基金经理[：:]\s*([^<\n]+)', text)
            if manager_match:
                detail["基金经理"] = manager_match.group(1).strip()
        
        if not detail["规模"]:
            scale_match = re.search(r'资产规模[：:]\s*([^<\n]+)', text)
            if scale_match:
                detail["规模"] = scale_match.group(1).strip()
        
        if not detail["成立日期"]:
            date_match = re.search(r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})', text)
            if date_match:
                detail["成立日期"] = date_match.group(1)
        
        return detail
        
    except Exception as e:
        print(f"[错误] 解析基金 {fund_code} 详情失败: {e}")
        return {
            "基金代码": fund_code,
            "基金名称": "",
            "基金类型": "",
            "成立日期": "",
            "管理公司": "",
            "基金经理": "",
            "规模": "",
            "评级": ""
        }


# 测试入口
if __name__ == "__main__":
    print("=" * 50)
    print("基金爬虫模块测试")
    print("=" * 50)
    
    # 测试获取基金列表
    print("\n[测试1] 获取基金列表（前5条）...")
    fund_list = get_fund_list()
    if not fund_list.empty:
        print(fund_list.head())
    
    # 测试获取排行
    print("\n[测试2] 获取基金排行（前5条）...")
    ranking = get_fund_ranking(top_n=5)
    if not ranking.empty:
        print(ranking.head())
    
    # 测试获取历史净值
    print("\n[测试3] 获取基金 000001 历史净值（最近5条）...")
    history = get_fund_history("000001")
    if not history.empty:
        print(history.head())
    
    # 测试获取基金详情
    print("\n[测试4] 获取基金 000001 详情...")
    detail = get_fund_detail("000001")
    print(detail)
