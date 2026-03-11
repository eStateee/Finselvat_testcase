import json
import base64
import uuid
import os
from datetime import datetime
from app.crypto import canonical_json_message, calc_transaction_hash, calc_transaction_sign, canonical_json_transactions_data, calc_signed_api_sign, canonical_json_transaction
from app.schemas import SignedApiData, TransactionsData, Transaction, Message

def save_example(filename, data):
    with open(os.path.join("examples", filename), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def build_incoming_202_valid():
    msg_payload = {"BankGuaranteeHash": "example-hash-of-bg", "status": "accepted"}
    payload_b64 = base64.b64encode(json.dumps(msg_payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('utf-8')
    
    msg_dict = {
        "Data": payload_b64,
        "SenderBranch": "SYSTEM_A",
        "ReceiverBranch": "SYSTEM_B",
        "InfoMessageType": 202,
        "MessageTime": "2024-05-20T12:00:00Z",
        "ChainGuid": str(uuid.uuid4()),
        "PreviousTransactionHash": "SOMEHASHPREVIOUS",
        "Metadata": None
    }
    
    msg_b64 = base64.b64encode(canonical_json_message(msg_dict).encode('utf-8')).decode('utf-8')
    
    tx_dict = {
        "TransactionType": 9,
        "Data": msg_b64,
        "TransactionTime": "2024-05-20T12:00:00Z",
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        "Metadata": None,
        "TransactionIn": None,
        "TransactionOut": None
    }
    
    tx_hash = calc_transaction_hash(tx_dict)
    tx_sign = calc_transaction_sign(tx_hash)
    
    tx_dict["Hash"] = tx_hash
    tx_dict["Sign"] = tx_sign
    
    txs_data = {"Transactions": [tx_dict], "Count": 1}
    txs_data_b64 = base64.b64encode(canonical_json_transactions_data(txs_data).encode('utf-8')).decode('utf-8')
    
    signed_api = {
        "Data": txs_data_b64,
        "Sign": calc_signed_api_sign(txs_data_b64),
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8')
    }
    save_example("incoming_202_valid.json", signed_api)
    return signed_api, tx_dict

def build_incoming_202_bad_hash(valid_signed_api, tx_dict):
    # We mutate the Hash
    bad_tx_dict = tx_dict.copy()
    bad_tx_dict["Hash"] = "BADHASH00000000000000000000000000"
    
    txs_data = {"Transactions": [bad_tx_dict], "Count": 1}
    txs_data_b64 = base64.b64encode(canonical_json_transactions_data(txs_data).encode('utf-8')).decode('utf-8')
    
    signed_api = {
        "Data": txs_data_b64,
        "Sign": calc_signed_api_sign(txs_data_b64),
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8')
    }
    save_example("incoming_202_bad_hash.json", signed_api)

def build_incoming_203_valid():
    msg_payload = {"BankGuaranteeHash": "example-hash-of-bg", "status": "rejected", "reason": "No funds"}
    payload_b64 = base64.b64encode(json.dumps(msg_payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('utf-8')
    
    msg_dict = {
        "Data": payload_b64,
        "SenderBranch": "SYSTEM_A",
        "ReceiverBranch": "SYSTEM_B",
        "InfoMessageType": 203,
        "MessageTime": "2024-05-20T13:00:00Z",
        "ChainGuid": str(uuid.uuid4()),
        "PreviousTransactionHash": "SOMEHASHPREVIOUS",
        "Metadata": None
    }
    
    msg_b64 = base64.b64encode(canonical_json_message(msg_dict).encode('utf-8')).decode('utf-8')
    
    tx_dict = {
        "TransactionType": 9,
        "Data": msg_b64,
        "TransactionTime": "2024-05-20T13:00:00Z",
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        "Metadata": None,
        "TransactionIn": None,
        "TransactionOut": None
    }
    
    tx_hash = calc_transaction_hash(tx_dict)
    tx_sign = calc_transaction_sign(tx_hash)
    
    tx_dict["Hash"] = tx_hash
    tx_dict["Sign"] = tx_sign
    
    txs_data = {"Transactions": [tx_dict], "Count": 1}
    txs_data_b64 = base64.b64encode(canonical_json_transactions_data(txs_data).encode('utf-8')).decode('utf-8')
    
    signed_api = {
        "Data": txs_data_b64,
        "Sign": calc_signed_api_sign(txs_data_b64),
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8')
    }
    save_example("incoming_203_valid.json", signed_api)

if __name__ == "__main__":
    valid_api, tx_dict = build_incoming_202_valid()
    build_incoming_202_bad_hash(valid_api, tx_dict)
    build_incoming_203_valid()
    print("Examples generated successfully.")
