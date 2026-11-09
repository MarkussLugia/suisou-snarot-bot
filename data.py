import time
from typing import Literal

import requests
from pydantic import BaseModel


class SnarotJSONCardData(BaseModel):
    # 卡牌的名称。
    name: str
    # <可选> 卡牌的描述文本。
    desc: str | None = None
    # 卡牌的画师。
    illust: str
    # 指向卡牌高清图片的相对路径。
    img: str
    # 指向卡牌网页缩略图的相对路径。
    thu: str
    # 卡牌的数字。0 代表当前卡牌没有数字。
    number: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # 能够匹配的场地颜色。"u"代表此卡牌出牌不受颜色限制。
    applyColor: Literal["r", "g", "b", "y", "u"]
    # 此卡牌更新的场地颜色。"s"代表由出牌者指定更新的颜色，"n"代表此卡牌不更新颜色。
    updateColor: Literal["r", "g", "b", "y", "s", "n"]
    # 打出后，将此卡牌加入巨塔。
    addToTower: bool
    # 打出后，反转出牌顺序。
    reverse: bool
    # 打出后，清除自身未生效的抽卡预言。
    clearAttack: bool
    # 打出后，下一位玩家的出牌将被跳过一次。
    disable: bool
    # 打出后，对下一位玩家附加抽卡预言。0 代表不启用。
    attackDraw: int
    # 对下一位玩家附加抽卡预言的延迟回合。0 代表立即生效。
    attackDelay: int
    # 打出后，对当前玩家进行抽卡惩罚。
    selfDraw: int
    # 打出后，开始巨塔崩塌环节。
    collapse: bool


class SnarotJSON(BaseModel):
    list: list[SnarotJSONCardData]


def get_data_from_json(
    url: str,
    conn_timeout: float = 5,
    read_timeout: float = 15,
    total_attempts: int = 3,
    retry_delay: float = 0.5,
) -> SnarotJSON:
    for attempt in range(1, total_attempts + 1):
        try:
            response = requests.get(url, timeout=(conn_timeout, read_timeout))
            return SnarotJSON.model_validate(response.json())
        except (requests.RequestException, requests.HTTPError, ValueError) as e:
            print(f"获取 {url} 失败：{type(e).__name__}")
            print(e)
            print(f"第 {attempt}/{total_attempts} 次，{retry_delay:.1f}s 后重试")
            if attempt < total_attempts:
                time.sleep(retry_delay)

    raise RuntimeError("无法获取卡牌列表。")
