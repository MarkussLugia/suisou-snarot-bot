import time
import traceback
from asyncio import Task

import requests


def format_exception(task: Task) -> str:
    if task.cancelled():
        return ""
    detail = ""
    error = task.exception()
    if error is not None:
        detail += "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        )
    return detail


def retryable_get(
    url: str,
    conn_timeout: float = 5,
    read_timeout: float = 20,
    total_attempts: int = 3,
    retry_delay: float = 0.5,
) -> requests.Response:
    for attempt in range(1, total_attempts + 1):
        try:
            response = requests.get(url, timeout=(conn_timeout, read_timeout))
            response.raise_for_status()
            return response
        except (requests.RequestException, requests.HTTPError) as e:
            print(f"GET {url} 失败：{type(e).__name__}")
            print(e)
            print(f"第 {attempt}/{total_attempts} 次，{retry_delay:.1f}s 后重试")
            if attempt < total_attempts:
                time.sleep(retry_delay)
    raise RuntimeError


def concat_URL(base: str, url: str) -> str:
    if base[-1] == "/":
        base = base[:-1]
    if url[0] != "/":
        url = "/" + url
    return base + url
