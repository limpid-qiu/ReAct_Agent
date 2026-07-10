from datetime import datetime
import os
import random
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
import requests
from utils.logger_handler import logger
from rag.rag_service import RagSummarizeService
from langchain_core.tools import tool

from utils.path_tool import get_abs_path

from app.core.request_context import get_current_request_context


rag = RagSummarizeService()
user_ids = ["1001", "1002", "1003", "1004", "1005", "1006", "1007", "1008", "1009", "1010"]
external_data = {}

load_dotenv()
AMAP_KEY = os.getenv("AMAP_KEY")

def get_city_adcode(city: str) -> str:
    """
    Get the administrative code (adcode) for a given city using the AMap API.
    """
    response = requests.get(
        "https://restapi.amap.com/v3/geocode/geo",
        params={
            "key": AMAP_KEY,
            "address": city,
            "output": "JSON",
        },
        timeout=(5, 15),
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "1" or not data.get("geocodes"):
        raise ValueError(f"未找到城市：{city}，原因：{data.get('info')}")

    return data["geocodes"][0]["adcode"]

@tool(description="获取指定城市的天气信息")
def get_weather(city: str) -> str:
    try:
        adcode = get_city_adcode(city)

        response = requests.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={
                "key": AMAP_KEY,
                "city": adcode,
                "extensions": "base",
                "output": "JSON",
            },
            timeout=(5, 15),
        )
        response.raise_for_status()
        data = response.json()

        live = data["lives"][0]

        return (
            f"{live.get('province')}{live.get('city')}当前天气："
            f"{live.get('weather')}，"
            f"气温{live.get('temperature')}℃，"
            f"湿度{live.get('humidity')}%，"
            f"{live.get('winddirection')}风，"
            f"风力{live.get('windpower')}级。"
            f"发布时间：{live.get('reporttime')}。"
        )
    except Exception as e:
        logger.error(f"获取{city}天气失败：{e}")

@tool(description="基于知识库的问答")
def rag_summarize(query: str) -> str:
    """
    Perform a RAG (Retrieval-Augmented Generation) summarization based on the provided query.

    Args:
        query (str): The query string to search for relevant documents and generate a summary.

    Returns:
        str: The generated summary or an error message if no relevant documents are found.
    """
    context = get_current_request_context()
    return rag.rag_summarize(
        query=query,
        context=context,
    )

@tool(description="获取用户ID")
def get_user_id() -> str:
    """
    获取用户ID
    """
    return random.choice(user_ids)

@tool(description="获取当前月份")
def get_current_month() -> str:
    """
    获取当前月份
    """
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m")

def generate_external_data():
    """
    {
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        "user_id": {
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            "month" : {"特征": xxx, "效率": xxx, ...}
            ...
        },
        ...
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abs_path("data/external/records.csv")

    if not os.path.exists(external_data_path):
        raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

    with open(external_data_path, "r", encoding="utf-8") as f:
        for line in f.readlines()[1:]:
            arr: list[str] = line.strip().split(",")

            user_id: str = arr[0].replace('"', "")
            feature: str = arr[1].replace('"', "")
            efficiency: str = arr[2].replace('"', "")
            consumables: str = arr[3].replace('"', "")
            comparison: str = arr[4].replace('"', "")
            time: str = arr[5].replace('"', "")

            if user_id not in external_data:
                external_data[user_id] = {}

            external_data[user_id][time] = {
                "特征": feature,
                "效率": efficiency,
                "耗材": consumables,
                "对比": comparison,
            }

@tool(description="从外部系统中获取指定用户在指定月份的使用记录，以纯字符串形式返回， 如果未检索到返回空字符串")
def fetch_external_data(user_id: str, month: str) -> str:
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(f"[fetch_external_data]未能检索到用户：{user_id}在{month}的使用记录数据")
        return ""

@tool(description="无入参，无返回值，调用后触发中间件自动为报告生成的场景动态注入上下文信息，为后续提示词切换提供上下文信息")
def fill_context_for_report():
    return "fill_context_for_report已调用"

if __name__ == "__main__":
    res1 = get_current_month.invoke({})
    print(res1)
    res2 = fetch_external_data.invoke({"user_id": "1001", "month": "2025-10"})
    print(res2)
