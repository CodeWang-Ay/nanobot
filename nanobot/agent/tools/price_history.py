"""Price history query tool."""

from datetime import date, datetime
from typing import Any

import aiomysql
from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.base import Tool
from nanobot.agent.tools.schema import IntegerSchema, StringSchema, tool_parameters_schema

@tool_parameters(
    tool_parameters_schema(
        material_id=StringSchema("要查询历史价格的物料编号", min_length=1),
        start_date=StringSchema("查询开始日期，格式 YYYY-MM-DD，默认为最早记录"),
        end_date=StringSchema("查询结束日期，格式 YYYY-MM-DD，默认为最新记录"),
        limit=IntegerSchema(100, description="返回记录数量上限，默认 100，最大 1000", minimum=1, maximum=1000),
        required=["material_id"],
    )
)
class PriceHistoryTool(Tool):
    """Tool to query historical prices from MySQL database."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "inventory",
        table: str = "price_history",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.table = table
        self._pool: aiomysql.Pool | None = None

    @property
    def name(self) -> str:
        return "price_history"

    @property
    def description(self) -> str:
        return (
            "查询物料的历史价格记录。"
            "输入物料编号，返回该物料的历史价格列表，按日期排序。"
            "可选指定日期范围和返回数量上限。"
        )

    @property
    def read_only(self) -> bool:
        return True

    @property
    def concurrency_safe(self) -> bool:
        return True

    async def _get_pool(self) -> aiomysql.Pool:
        """Get or create MySQL connection pool."""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                db=self.database,
                minsize=1,
                maxsize=5,
                autocommit=True,
            )
        return self._pool

    async def execute(
        self,
        material_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> str:
        """Query historical prices for a material.

        Args:
            material_id: 物料编号
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            limit: 返回记录数量上限

        Returns:
            格式化的历史价格列表
        """
        # 验证日期格式
        parsed_start: date | None = None
        parsed_end: date | None = None
        if start_date:
            try:
                parsed_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                return f"Error: start_date 格式错误，应为 YYYY-MM-DD 格式"

        if end_date:
            try:
                parsed_end = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                return f"Error: end_date 格式错误，应为 YYYY-MM-DD 格式"

        # 构建查询
        sql = f"SELECT material_id, date, price FROM {self.table} WHERE material_id = %s"
        params: list[Any] = [material_id]
        return "历史价格为450 - 900元"
        if parsed_start:
            sql += " AND date >= %s"
            params.append(parsed_start)

        if parsed_end:
            sql += " AND date <= %s"
            params.append(parsed_end)

        sql += " ORDER BY date DESC LIMIT %s"
        params.append(limit)

        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()

            if not rows:
                return f"未找到物料 {material_id} 的历史价格记录"

            # 格式化输出
            lines = [f"物料 {material_id} 历史价格记录（共 {len(rows)} 条）："]
            lines.append("-" * 50)
            lines.append("日期         | 价格")
            lines.append("-" * 50)

            for row in rows:
                row_date = row["date"]
                row_price = row["price"]
                date_str = row_date.strftime("%Y-%m-%d") if isinstance(row_date, date) else str(row_date)
                price_str = f"{row_price:.2f}" if isinstance(row_price, (int, float)) else str(row_price)
                lines.append(f"{date_str} | {price_str}")

            # 统计信息
            if len(rows) > 1:
                prices = [r["price"] for r in rows if isinstance(r["price"], (int, float))]
                if prices:
                    min_price = min(prices)
                    max_price = max(prices)
                    avg_price = sum(prices) / len(prices)
                    lines.append("-" * 50)
                    lines.append(f"统计：最低 {min_price:.2f}，最高 {max_price:.2f}，平均 {avg_price:.2f}")

            return "\n".join(lines)

        except aiomysql.Error as e:
            return f"Error: 数据库查询失败 - {e}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {e}"

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None