from pydantic import BaseModel, ConfigDict, Field, field_validator
import base64
from typing import Optional, List
from datetime import datetime

def validate_base64_string(v: str) -> str:
    if not isinstance(v, str):
        raise ValueError("Must be string")
    try:
        base64.b64decode(v, validate=True)
        return v
    except Exception:
        raise ValueError("Invalid Base64 string")

class SearchRequest(BaseModel):
    StartDate: datetime
    EndDate: datetime
    Limit: int
    Offset: int

    @field_validator('Limit')
    @classmethod
    def check_limit(cls, v: int) -> int:
        if v <= 0 or v > 1000:
            raise ValueError("Limit must be > 0 and <= 1000")
        return v

class SignedApiData(BaseModel):
    Data: str
    Sign: str
    SignerCert: str

    @field_validator('Data', 'Sign', 'SignerCert')
    @classmethod
    def validate_b64(cls, v: str) -> str:
        return validate_base64_string(v)

class Message(BaseModel):
    Data: str
    SenderBranch: str
    ReceiverBranch: str
    InfoMessageType: int
    MessageTime: datetime
    ChainGuid: str
    PreviousTransactionHash: Optional[str] = None
    Metadata: Optional[str] = None

    @field_validator('Data')
    @classmethod
    def validate_b64(cls, v: str) -> str:
        return validate_base64_string(v)

class Transaction(BaseModel):
    TransactionType: int
    Data: str
    Hash: Optional[str] = None
    Sign: Optional[str] = None
    SignerCert: str
    TransactionTime: datetime
    Metadata: Optional[str] = None
    TransactionIn: Optional[str] = None
    TransactionOut: Optional[str] = None

    @field_validator('Data', 'SignerCert')
    @classmethod
    def validate_b64(cls, v: str) -> str:
        return validate_base64_string(v)

    @field_validator('Sign')
    @classmethod
    def validate_b64_optional(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            return validate_base64_string(v)
        return v

class TransactionsData(BaseModel):
    Transactions: List[Transaction]
    Count: int
