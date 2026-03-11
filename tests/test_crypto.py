"""
Тесты для модуля app/crypto.py: каноническая сериализация, хэш, подпись.
"""
import pytest
import base64
import hashlib
from app.crypto import (
    canonical_json_transaction,
    canonical_json_message,
    canonical_json_transactions_data,
    calc_transaction_hash,
    calc_transaction_sign,
    calc_signed_api_sign,
)


class TestCanonicalJsonTransaction:
    def test_field_order_and_null_values(self):
        """Порядок полей Transaction должен строго соответствовать ТЗ; null-поля присутствуют."""
        tx = {
            "Data": "YmFzZTY0",
            "SignerCert": "Y2VydA==",
            "TransactionType": 9,
            "TransactionTime": "2024-05-20T10:00:00Z",
            "Metadata": None,
        }
        c_json = canonical_json_transaction(tx)
        expected = (
            '{"TransactionType":9,"Data":"YmFzZTY0","Metadata":null,'
            '"TransactionTime":"2024-05-20T10:00:00Z","Sign":null,'
            '"SignerCert":"Y2VydA==","Hash":null,"TransactionIn":null,"TransactionOut":null}'
        )
        assert c_json == expected

    def test_no_spaces(self):
        tx = {"TransactionType": 9, "Data": "dA=="}
        c_json = canonical_json_transaction(tx)
        assert " " not in c_json


class TestCanonicalJsonMessage:
    def test_field_order(self):
        msg = {
            "ChainGuid": "abc",
            "Data": "dA==",
            "SenderBranch": "SYSTEM_A",
            "ReceiverBranch": "SYSTEM_B",
            "InfoMessageType": 202,
            "MessageTime": "2024-05-20T12:00:00Z",
            "PreviousTransactionHash": None,
            "Metadata": None,
        }
        c_json = canonical_json_message(msg)
        keys = [k.strip('"') for k in c_json.split(':')[0::2]]
        # Первый ключ — Data, последний — Metadata
        assert c_json.startswith('{"Data"')
        assert c_json.endswith('"Metadata":null}')

    def test_null_fields_present(self):
        msg = {
            "Data": "dA==",
            "SenderBranch": "SYSTEM_A",
            "ReceiverBranch": "SYSTEM_B",
            "InfoMessageType": 202,
            "MessageTime": "2024-05-20T12:00:00Z",
            "ChainGuid": "abc",
        }
        c_json = canonical_json_message(msg)
        assert '"PreviousTransactionHash":null' in c_json
        assert '"Metadata":null' in c_json


class TestCanonicalJsonTransactionsData:
    def test_structure(self):
        data = {"Transactions": [], "Count": 0}
        c_json = canonical_json_transactions_data(data)
        assert c_json == '{"Transactions":[],"Count":0}'

    def test_transactions_order(self):
        tx = {
            "TransactionType": 9,
            "Data": "dA==",
            "TransactionTime": "2024-05-20T10:00:00Z",
            "SignerCert": "Y2VydA==",
        }
        data = {"Transactions": [tx], "Count": 1}
        c_json = canonical_json_transactions_data(data)
        assert '"Transactions"' in c_json
        assert '"Count":1' in c_json


class TestCalcTransactionHash:
    def test_returns_upper_hex(self):
        tx = {
            "TransactionType": 9,
            "Data": "YmFzZTY0",
            "SignerCert": "Y2VydA==",
            "TransactionTime": "2024-05-20T10:00:00Z",
            "Metadata": None,
        }
        hash_hex = calc_transaction_hash(tx)
        assert hash_hex == hash_hex.upper()
        assert len(hash_hex) == 64

    def test_hash_changes_with_data(self):
        tx1 = {"TransactionType": 9, "Data": "YQ==", "TransactionTime": "2024-05-20T10:00:00Z", "SignerCert": "Y2VydA=="}
        tx2 = {"TransactionType": 9, "Data": "Yg==", "TransactionTime": "2024-05-20T10:00:00Z", "SignerCert": "Y2VydA=="}
        assert calc_transaction_hash(tx1) != calc_transaction_hash(tx2)

    def test_hash_ignores_sign_value(self):
        """Hash не зависит от поля Sign (оно обнуляется при вычислении)."""
        tx = {
            "TransactionType": 9,
            "Data": "YmFzZTY0",
            "TransactionTime": "2024-05-20T10:00:00Z",
            "SignerCert": "Y2VydA==",
            "Sign": "ZmFrZXNpZ24=",
        }
        tx_no_sign = tx.copy()
        tx_no_sign["Sign"] = ""
        assert calc_transaction_hash(tx) == calc_transaction_hash(tx_no_sign)

    def test_hash_ignores_hash_value(self):
        """Hash не зависит от текущего значения поля Hash (оно обнуляется)."""
        tx = {
            "TransactionType": 9,
            "Data": "YmFzZTY0",
            "TransactionTime": "2024-05-20T10:00:00Z",
            "SignerCert": "Y2VydA==",
            "Hash": "SOMEPREVIOUSHASH",
        }
        tx_no_hash = tx.copy()
        tx_no_hash.pop("Hash")
        assert calc_transaction_hash(tx) == calc_transaction_hash(tx_no_hash)


class TestCalcTransactionSign:
    def test_sign_is_base64_of_hash_bytes(self):
        hash_hex = calc_transaction_hash({
            "TransactionType": 9,
            "Data": "YmFzZTY0",
            "TransactionTime": "2024-05-20T10:00:00Z",
            "SignerCert": "Y2VydA==",
        })
        sign_b64 = calc_transaction_sign(hash_hex)
        decoded = base64.b64decode(sign_b64)
        assert decoded == bytes.fromhex(hash_hex)


class TestCalcSignedApiSign:
    def test_sign_is_sha256_base64(self):
        data = "YQ=="
        expected = base64.b64encode(hashlib.sha256(data.encode('utf-8')).digest()).decode()
        assert calc_signed_api_sign(data) == expected

    def test_different_data_different_sign(self):
        assert calc_signed_api_sign("YQ==") != calc_signed_api_sign("Yg==")

    def test_deterministic(self):
        data = "dGVzdA=="
        assert calc_signed_api_sign(data) == calc_signed_api_sign(data)
