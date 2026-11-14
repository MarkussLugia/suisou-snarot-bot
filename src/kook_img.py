"""
用于 kook 平台的 image url 模块
包含 kv 存储类 URLCacheKV 和创建缓存方法 get_image_link
"""

import json
import os
import tempfile
import time
from pathlib import Path

import requests

from shared import concat_URL, retryable_get

KOOK_API_BASE = "https://www.kookapp.cn/api"
KOOK_ASSET_CREATE_URL = concat_URL(KOOK_API_BASE, "/v3/asset/create")

UPLOAD_TIMEOUT = (5, 30)


class URLCacheKV:
    def __init__(self, raw: str | None = None) -> None:
        self._data: dict[str, str] = self.__parse_text(raw) if raw else {}

    # 读取、写入、筛选、删除
    def get(self, key: str) -> str:
        """如果未命中，则返回原始链接。"""
        if key in self._data:
            return self._data[key]
        else:
            return key

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def list_miss(self, keys: list[str]) -> list[str]:
        """列出未命中的 key。"""
        return [key for key in keys if key not in self._data]

    def remove(self, key: str) -> None:
        del self._data[key]

    # 序列化 json 处理
    @staticmethod
    def __parse_text(raw: str) -> dict[str, str]:
        raw = raw.strip()
        if not raw:
            return {}

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 损坏：{e}") from e

        if not isinstance(data, dict):
            raise TypeError("JSON 不符合 URLCacheKV 格式。")

        for key, value in data.items():
            if not isinstance(value, str):
                raise TypeError(
                    f"JSON 不符合 URLCacheKV 格式：key {key} 的值不是字符串。"
                )
        return data

    @classmethod
    def from_string(cls, raw: str) -> "URLCacheKV":
        """从 json 字符串初始化。"""
        return cls(raw)

    def to_string(self) -> str:
        """序列化为 json 字符串。"""
        return json.dumps(
            self._data,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

    # 文件读写
    @classmethod
    def from_file(cls, path: str | os.PathLike[str]) -> "URLCacheKV":
        """读取 json 文件并初始化 KV 缓存。"""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except FileNotFoundError:
            print("文件不存在，创建了空的 KV 缓存")
            return cls()
        return cls.from_string(text)

    def to_file(self, path: str | os.PathLike[str]) -> None:
        """将 KV 缓存内容写出为 json 文件。"""
        file_write_tmp(path, f"{self.to_string()}\n")


def get_image_link(
    link: str,
    token: str,
) -> str:
    """
    从原始地址下载图片，上传到 kook 并返回缓存的文件链接
    """
    print(f"从 {link} 下载原始图片")

    ext = link.split(".")[-1]
    image = retryable_get(link, total_attempts=5)

    print("向 kook api 上传图片")
    kook_url = upload_image(image.content, token, f"image.{ext}")

    return kook_url


def upload_image(image: bytes, token: str, filename: str) -> str:
    response = requests.post(
        KOOK_ASSET_CREATE_URL,
        headers={"Authorization": f"Bot {token}"},
        files={"file": (filename, image)},
        timeout=UPLOAD_TIMEOUT,
    )
    response.raise_for_status()
    remaining = int(response.headers["X-Rate-Limit-Remaining"])
    wait = int(response.headers["X-Rate-Limit-Reset"])
    print(f"Rate-Limit: remaining {remaining}, reset in {wait}s")
    if remaining <= 2:
        print(f"kook api 操作频率接近上限，暂停 {wait} 秒")
        time.sleep(wait)
    return response.json()["data"]["url"]


def file_write_tmp(
    path: str | os.PathLike[str], content: str, *, encoding: str = "utf-8"
):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, target)
    except OSError:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise
