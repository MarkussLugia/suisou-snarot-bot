import os

import requests
from dotenv import load_dotenv

from data import get_data_from_json
from kook_img import URLCacheKV, get_image_link
from shared import concat_URL

# 加载 bot 认证令牌
load_dotenv()
BOT_ACCESS_TOKEN = os.environ.get("BOT_ACCESS_TOKEN")
if not BOT_ACCESS_TOKEN:
    raise ValueError("需要在 env 中指定 BOT_ACCESS_TOKEN")

# 加载卡牌数据
SNAROT_BASE_URL = "https://snarot.siltra.top/cards/"
CARDS_BASIC_JSON_URL = concat_URL(SNAROT_BASE_URL, "/cards_basic.json")
print(f"正在加载卡牌数据：{CARDS_BASIC_JSON_URL}")
CARDS_BASIC_JSON = get_data_from_json(CARDS_BASIC_JSON_URL)

# 初始化卡牌图片缓存
IMAGE_URL_CACHE_FILE = os.path.join("botcache", "kook_url.json")
IMAGE_URL_CACHE = URLCacheKV.from_file(IMAGE_URL_CACHE_FILE)
missing_cache_urls = IMAGE_URL_CACHE.list_miss(
    [concat_URL(SNAROT_BASE_URL, card.img) for card in CARDS_BASIC_JSON.list]
)
if missing_cache_urls:
    print(f"有 {len(missing_cache_urls)} 个图片链接未缓存。现在开始创建缓存。")
    for index, url in enumerate(missing_cache_urls):
        print(f"正在创建缓存：共 {len(missing_cache_urls)} 个，第 {index + 1} 个")
        try:
            uploaded_url = get_image_link(url, BOT_ACCESS_TOKEN)
            IMAGE_URL_CACHE.set(url, uploaded_url)
            IMAGE_URL_CACHE.to_file(IMAGE_URL_CACHE_FILE)
        except (requests.RequestException, requests.HTTPError, RuntimeError) as e:
            print(f"创建缓存出错：{e}")

print("进入 bot 启动流程")
