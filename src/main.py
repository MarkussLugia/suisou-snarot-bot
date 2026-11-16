import asyncio
import os

import requests
from aiohttp import ClientError
from dotenv import load_dotenv
from khl import Bot, Message
from khl.card import Card, CardMessage, Element, Module
from khl.user import User

from data import get_data_from_json
from kook_img import URLCacheKV, get_image_link
from shared import concat_URL

print()
print("-__--'''--___-'| SNAROT SLUGBOT |'-___--'''--__-")
print()

# 加载 bot 认证令牌
print("'.' 正在加载 BOT_ACCESS_TOKEN")
load_dotenv()
BOT_ACCESS_TOKEN = os.environ.get("BOT_ACCESS_TOKEN")
if not BOT_ACCESS_TOKEN:
    raise ValueError("机器人认证令牌加载失败，需要在 env 中指定 BOT_ACCESS_TOKEN")
print(".'. - 已加载令牌")

# 加载卡牌数据
SNAROT_BASE_URL = "https://snarot.siltra.top/cards/"
CARDS_BASIC_JSON_URL = concat_URL(SNAROT_BASE_URL, "/cards_basic.json")
print(f"'.' 正在获取卡牌数据：{CARDS_BASIC_JSON_URL}")
CARDS_BASIC_JSON = get_data_from_json(CARDS_BASIC_JSON_URL)
print(f".'. - 已加载 {len(CARDS_BASIC_JSON.list)} 张卡牌")

# 初始化卡牌图片缓存
IMAGE_URL_CACHE_FILE = os.path.join("botcache", "kook_url.json")
IMAGE_URL_CACHE = URLCacheKV.from_file(IMAGE_URL_CACHE_FILE)
missing_cache_urls = IMAGE_URL_CACHE.list_miss(
    [concat_URL(SNAROT_BASE_URL, card.img) for card in CARDS_BASIC_JSON.list]
)
if missing_cache_urls:
    print(f"--- 有 {len(missing_cache_urls)} 个图片链接未缓存。现在开始创建缓存。")
    for index, url in enumerate(missing_cache_urls):
        print(
            f">>> 正在创建图片缓存：共 {len(missing_cache_urls)} 个，第 {index + 1} 个"
        )
        try:
            uploaded_url = get_image_link(url, BOT_ACCESS_TOKEN)
            IMAGE_URL_CACHE.set(url, uploaded_url)
            IMAGE_URL_CACHE.to_file(IMAGE_URL_CACHE_FILE)
        except (requests.RequestException, requests.HTTPError, RuntimeError) as e:
            print(f"创建缓存出错：{e}")

print("'.' 开始初始化 bot 功能")

bot = Bot(token=BOT_ACCESS_TOKEN)
games = {}
user_name_cache = {}


async def get_display_name(user_id) -> str:
    if user_id in user_name_cache:
        return user_name_cache[user_id]
    try:
        user = await bot.client.fetch_user(user_id)
        name = user.nickname if user.nickname else user.username
        user_name_cache[user_id] = name
        return name
    except (ClientError, ValueError, AttributeError) as e:
        print(f"获取用户 {user_id} 名字失败: {e}")
        return user_id


def update_username_cache(user: User):
    try:
        name = user.nickname if user.nickname else user.username
        user_name_cache[user.id] = name
    except AttributeError:
        return


@bot.command(name="whoami", prefixes=["/"])
async def whoami(msg: Message):
    update_username_cache(msg.author)
    username = await get_display_name(msg.author_id)
    await msg.reply(username)


print(".'. 启动 kook bot")
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
bot.run()
