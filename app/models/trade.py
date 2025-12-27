from pydantic import BaseModel, Field
from typing import Optional

class Trade(BaseModel):
    timestamp: int
    side: str
    price: float
    size: float

    conditionId: Optional[str] = None
    title: Optional[str] = None
    slug: Optional[str] = None
    icon: Optional[str] = None
    outcome: Optional[str] = None

    transactionHash: Optional[str] = None
    proxyWallet: Optional[str] = None

    def key(self) -> str:
        # ключ для дедупа (transactionHash лучше всего, но иногда может быть None)
        if self.transactionHash:
            return self.transactionHash
        return f"{self.timestamp}:{self.proxyWallet}:{self.conditionId}:{self.side}:{self.price}:{self.size}"
