import pytest
import base64
from app.crypto import (
    canonical_json_transaction,
    calc_transaction_hash,
    calc_transaction_sign,
    calc_signed_api_sign
)

def test_canonical_json_transaction_order_and_null():
    tx = {
        "Data": "YmFzZTY0",
        "SignerCert": "Y2VydA==",
        "TransactionType": 9,
        "TransactionTime": "2024-05-20T10:00:00Z",
        "Metadata": None
    }
    c_json = canonical_json_transaction(tx)
    expected = '{"TransactionType":9,"Data":"YmFzZTY0","Metadata":null,"TransactionTime":"2024-05-20T10:00:00Z","Sign":null,"SignerCert":"Y2VydA==","Hash":null,"TransactionIn":null,"TransactionOut":null}'
    assert c_json == expected

def test_calc_transaction_hash_and_sign():
    tx = {
        "TransactionType": 9,
        "Data": "YmFzZTY0",
        "SignerCert": "Y2VydA==",
        "TransactionTime": "2024-05-20T10:00:00Z",
        "Metadata": None
    }
    hash_hex = calc_transaction_hash(tx)
    assert hash_hex.isupper()
    
    sign_b64 = calc_transaction_sign(hash_hex)
    b_hash = base64.b64decode(sign_b64)
    assert b_hash == bytes.fromhex(hash_hex)

def test_calc_signed_api_sign():
    data1 = "YQ=="
    data2 = "Yg=="
    sign1 = calc_signed_api_sign(data1)
    sign2 = calc_signed_api_sign(data2)
    assert sign1 != sign2

def test_calc_signed_api_sign_predictable():
    import hashlib
    data = "YQ=="
    expected = base64.b64encode(hashlib.sha256(data.encode('utf-8')).digest()).decode()
    assert calc_signed_api_sign(data) == expected
