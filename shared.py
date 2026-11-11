import traceback
from asyncio import Task


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
