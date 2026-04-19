"""internet price query tool."""

from datetime import date, datetime
from typing import Any

from loguru import logger
import aiomysql
from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.schema import IntegerSchema, StringSchema, tool_parameters_schema


@tool_parameters(
    tool_parameters_schema(
        material_name=StringSchema("要查询互联网价格的物料名称", min_length=1),
        material_spec=StringSchema("要查询互联网价格的物料编码"),
        low_price=StringSchema("查询最低价格，默认为0元"),
        price_date=StringSchema("查询最高价格，默认为无上限"),
        limit=IntegerSchema(100, description="返回记录数量上限，默认 100，最大 1000", minimum=1, maximum=1000),
        required=["material_name"],
    )
)

class PriceInternetTool(Tool):
    def __init__(
        self,
        enable: bool = True  # 默认禁用，需要配置数据库连接后启用
    ):
        pass


    @property
    def name(self) -> str:
        return "price_internet"

    @property
    def description(self) -> str:
        return (
            "查询物料的互联网价格"
            "输入物料名称，物料规格返回该物料的的互联网参考价格"
            "可选指定价格范围和返回数量上限。"
        )

    @property
    def read_only(self) -> bool:
        return True

    @property
    def concurrency_safe(self) -> bool:
        return True
    
    async def execute(
        self,
        material_name: str,
        material_spec: str,
        low_price: str | None = None,
        high_price: str | None = None,
        limit: int = 100,
    ) -> str:
        """Query historical prices for a material.

        Args:
            material_name: 物料名称
            material_spec: 物料规格
            low_price: 最低价格
            high_price: 最高价格
            limit: 返回记录数量上限

        Returns:
            格式化的互联网价格列表
        """
        logger.info(f"互联网查询价格工具被调用: material_name: {material_name} material_spec: {material_spec}")
        query_keywords = material_name + material_spec
        try:

            return f"{query_keywords} 互联网价格为450 - 900元"

        except aiomysql.Error as e:
            return f"Error: 数据库查询失败 - {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"