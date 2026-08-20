"""认证验证器。

沿用旧版客户端的认证边界：Agent 不自行解析 JWT，而是调用 CSN 的
validate-doctor-token 接口确认 Token 有效性。验证成功后把 user_info
和原始 Authorization 封装成 AuthContext。
"""

from typing import Any

import httpx

from .context import AuthContext


class AuthenticationError(Exception):
    """客户端认证失败。"""


class AuthVerifier:
    """通过 CSN 统一认证服务验证 Authorization Token。"""

    def __init__(self, csn_url: str, timeout: float = 30.0):
        if not csn_url:
            raise ValueError("CSN_URL is required")
        self.csn_url = csn_url.rstrip("/")
        self.timeout = timeout

    async def verify(self, authorization: str | None) -> AuthContext:
        """验证 Bearer Token；失败时不允许进入 Agent Workflow。"""
        if not authorization:
            raise AuthenticationError("Missing Authorization header")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.csn_url}/v2/user-clinic-doctor/validate-doctor-token",
                    json={},
                    headers={"Authorization": authorization},
                )
                result: dict[str, Any] = response.json()
        except httpx.TimeoutException as exc:
            raise AuthenticationError("用户系统繁忙，请稍后重试") from exc
        except httpx.HTTPError as exc:
            raise AuthenticationError("用户系统繁忙，请稍后重试") from exc
        except ValueError as exc:
            raise AuthenticationError("Invalid token validation response") from exc

        if result.get("code") != 10000:
            raise AuthenticationError(result.get("msg", "Token validation failed"))

        user_info = result.get("resultObject") or {}
        if not isinstance(user_info, dict):
            user_info = {"raw": user_info}
        return AuthContext(authorization=authorization, user_info=user_info)
