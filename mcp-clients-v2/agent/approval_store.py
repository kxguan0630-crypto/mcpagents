"""保存待审批请求。

第一版使用内存存储，方便学习和本地运行。
以后接 Redis 时，只需要新增 RedisApprovalStore，不需要修改 Agent 的业务代码。
"""

from abc import ABC, abstractmethod

from .approval import ApprovalRequest


class ApprovalStore(ABC):
    """审批请求存储的最小接口。"""

    @abstractmethod
    async def save(self, request: ApprovalRequest) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, approval_id: str) -> ApprovalRequest | None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, approval_id: str) -> None:
        raise NotImplementedError


class InMemoryApprovalStore(ApprovalStore):
    """最简单的审批存储实现。"""

    def __init__(self) -> None:
        self._items: dict[str, ApprovalRequest] = {}

    async def save(self, request: ApprovalRequest) -> None:
        self._items[request.approval_id] = request

    async def get(self, approval_id: str) -> ApprovalRequest | None:
        return self._items.get(approval_id)

    async def delete(self, approval_id: str) -> None:
        self._items.pop(approval_id, None)
