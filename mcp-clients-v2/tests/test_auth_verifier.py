"""CSN 认证验证器测试。"""

import httpx
import pytest

from auth.verifier import AuthVerifier, AuthenticationError


@pytest.mark.asyncio
async def test_csn_success_returns_auth_context():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer real-token"
        return httpx.Response(200, json={"code": 10000, "resultObject": {"userId": 123}})

    verifier = AuthVerifier("http://csn.test")
    transport = httpx.MockTransport(handler)

    # 替换验证器内部 Client 的创建方式，避免测试访问真实 CSN。
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda **kwargs: original(transport=transport, **kwargs)
    try:
        context = await verifier.verify("Bearer real-token")
    finally:
        httpx.AsyncClient = original

    assert context.authorization == "Bearer real-token"
    assert context.user_info["userId"] == 123


@pytest.mark.asyncio
async def test_missing_token_is_rejected():
    verifier = AuthVerifier("http://csn.test")
    with pytest.raises(AuthenticationError):
        await verifier.verify(None)


@pytest.mark.asyncio
async def test_csn_non_success_code_is_rejected():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 401, "msg": "token expired"})

    verifier = AuthVerifier("http://csn.test")
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda **kwargs: original(transport=transport, **kwargs)
    try:
        with pytest.raises(AuthenticationError, match="token expired"):
            await verifier.verify("Bearer expired-token")
    finally:
        httpx.AsyncClient = original
