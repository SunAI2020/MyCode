from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict:
    """统一成功响应：{"code":0,"message":"ok","data":{...}}"""
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict:
    """统一失败响应：{"code":非0,"message":错误信息,"data":null}"""
    return {"code": code, "message": message, "data": data}
