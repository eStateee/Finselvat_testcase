import base64
import json
import hashlib
import logging
from collections import OrderedDict
from datetime import datetime

logger = logging.getLogger(__name__)


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%dT%H:%M:%SZ")
        return super().default(obj)


def _serialize_to_json(obj: OrderedDict) -> str:
    return json.dumps(obj, separators=(',', ':'), ensure_ascii=False, cls=CustomEncoder)


def to_ordered_transaction(obj: dict) -> OrderedDict:
    order = [
        "TransactionType", "Data", "Metadata", "TransactionTime",
        "Sign", "SignerCert", "Hash", "TransactionIn", "TransactionOut",
    ]
    ordered_dict = OrderedDict()
    for key in order:
        ordered_dict[key] = obj.get(key)
    return ordered_dict


def canonical_json_transaction(obj: dict) -> str:
    return _serialize_to_json(to_ordered_transaction(obj))


def canonical_json_transactions_data(obj: dict) -> str:
    ordered_dict = OrderedDict()
    ordered_dict["Transactions"] = [to_ordered_transaction(tx) for tx in obj.get("Transactions", [])]
    ordered_dict["Count"] = obj.get("Count", 0)
    return _serialize_to_json(ordered_dict)


def canonical_json_message(obj: dict) -> str:
    order = [
        "Data", "SenderBranch", "ReceiverBranch", "InfoMessageType",
        "MessageTime", "ChainGuid", "PreviousTransactionHash", "Metadata",
    ]
    ordered_dict = OrderedDict()
    for key in order:
        ordered_dict[key] = obj.get(key)
    return _serialize_to_json(ordered_dict)


def canonical_json_signed_api_data(obj: dict) -> str:
    """Каноническая сериализация SignedApiData: Data, Sign, SignerCert."""
    order = ["Data", "Sign", "SignerCert"]
    ordered_dict = OrderedDict()
    for key in order:
        ordered_dict[key] = obj.get(key)
    return _serialize_to_json(ordered_dict)


def calc_transaction_hash(transaction: dict) -> str:
    """SHA-256 (HEX UPPER) от канонического JSON транзакции с Hash=null, Sign=""."""
    tx_copy = transaction.copy()
    tx_copy["Hash"] = None
    tx_copy["Sign"] = ""
    c_json = canonical_json_transaction(tx_copy)
    return hashlib.sha256(c_json.encode('utf-8')).hexdigest().upper()


def calc_transaction_sign(hash_hex: str) -> str:
    """Эмуляция подписи: bytes.fromhex(hash_hex) → Base64."""
    b = bytes.fromhex(hash_hex)
    return base64.b64encode(b).decode('utf-8')


def calc_signed_api_sign(data_base64_str: str) -> str:
    """Эмуляция подписи ответа: SHA256(UTF8(Data_base64_str)) → Base64."""
    digest = hashlib.sha256(data_base64_str.encode('utf-8')).digest()
    return base64.b64encode(digest).decode('utf-8')
