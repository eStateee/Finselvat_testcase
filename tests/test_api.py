"""
Интеграционные тесты для REST API (FastAPI TestClient).
Используют временную файловую БД в tmp, изолированную от разработческой data/app.db.
"""
import pytest
import base64
import json
import os
import tempfile

# Устанавливаем путь к изолированной БД ДО импорта app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DB_PATH"] = _tmp_db.name

from fastapi.testclient import TestClient
from app.main import app
from app.crypto import (
    canonical_json_message,
    canonical_json_transactions_data,
    calc_transaction_hash,
    calc_transaction_sign,
    calc_signed_api_sign,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _make_outgoing_payload(start: str, end: str, limit: int = 100, offset: int = 0) -> dict:
    """Строит корректный SignedApiData для /api/messages/outgoing."""
    search = {"StartDate": start, "EndDate": end, "Limit": limit, "Offset": offset}
    search_b64 = base64.b64encode(
        json.dumps(search, separators=(',', ':')).encode('utf-8')
    ).decode('utf-8')
    sign = calc_signed_api_sign(search_b64)
    return {
        "Data": search_b64,
        "Sign": sign,
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
    }


def _make_incoming_payload(msg_type: int, bg_hash: str = "test-bg-hash", chain_guid: str = "11111111-1111-1111-1111-111111111111") -> dict:
    """Строит корректный SignedApiData для /api/messages/incoming с транзакцией типа msg_type."""
    msg_payload = {"BankGuaranteeHash": bg_hash}
    payload_b64 = base64.b64encode(
        json.dumps(msg_payload, separators=(',', ':')).encode('utf-8')
    ).decode('utf-8')

    msg_dict = {
        "Data": payload_b64,
        "SenderBranch": "SYSTEM_A",
        "ReceiverBranch": "SYSTEM_B",
        "InfoMessageType": msg_type,
        "MessageTime": "2024-05-20T12:00:00Z",
        "ChainGuid": chain_guid,
        "PreviousTransactionHash": None,
        "Metadata": None,
    }
    msg_b64 = base64.b64encode(canonical_json_message(msg_dict).encode('utf-8')).decode('utf-8')

    tx_dict = {
        "TransactionType": 9,
        "Data": msg_b64,
        "TransactionTime": "2024-05-20T12:00:00Z",
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        "Metadata": None,
        "TransactionIn": None,
        "TransactionOut": None,
    }
    tx_hash = calc_transaction_hash(tx_dict)
    tx_sign = calc_transaction_sign(tx_hash)
    tx_dict["Hash"] = tx_hash
    tx_dict["Sign"] = tx_sign

    txs_data = {"Transactions": [tx_dict], "Count": 1}
    txs_b64 = base64.b64encode(
        canonical_json_transactions_data(txs_data).encode('utf-8')
    ).decode('utf-8')
    return {
        "Data": txs_b64,
        "Sign": calc_signed_api_sign(txs_b64),
        "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
    }


# ─── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.text == "OK"


# ─── Outgoing ──────────────────────────────────────────────────────────────────

class TestOutgoing:
    def test_outgoing_seed_transaction_present(self, client):
        """После старта должна быть seed-транзакция 201 в диапазоне 2024 года."""
        payload = _make_outgoing_payload("2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z")
        resp = client.post("/api/messages/outgoing", json=payload)
        assert resp.status_code == 200

        body = resp.json()
        assert "Data" in body and "Sign" in body and "SignerCert" in body

        inner = json.loads(base64.b64decode(body["Data"]).decode('utf-8'))
        assert inner["Count"] >= 1

    def test_outgoing_empty_range(self, client):
        """Запрос за пустой период возвращает Count=0."""
        payload = _make_outgoing_payload("2020-01-01T00:00:00Z", "2020-12-31T23:59:59Z")
        resp = client.post("/api/messages/outgoing", json=payload)
        assert resp.status_code == 200
        inner = json.loads(base64.b64decode(resp.json()["Data"]).decode('utf-8'))
        assert inner["Count"] == 0
        assert inner["Transactions"] == []

    def test_outgoing_invalid_base64(self, client):
        payload = {"Data": "not_valid_base64!!!", "Sign": "YQ==", "SignerCert": "YQ=="}
        resp = client.post("/api/messages/outgoing", json=payload)
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_outgoing_invalid_limit(self, client):
        """Limit=0 должен вернуть 400."""
        search = {"StartDate": "2024-01-01T00:00:00Z", "EndDate": "2024-12-31T23:59:59Z", "Limit": 0, "Offset": 0}
        search_b64 = base64.b64encode(
            json.dumps(search, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')
        payload = {
            "Data": search_b64,
            "Sign": calc_signed_api_sign(search_b64),
            "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        }
        resp = client.post("/api/messages/outgoing", json=payload)
        assert resp.status_code == 400

    def test_outgoing_limit_over_max(self, client):
        """Limit=1001 должен вернуть 400."""
        search = {"StartDate": "2024-01-01T00:00:00Z", "EndDate": "2024-12-31T23:59:59Z", "Limit": 1001, "Offset": 0}
        search_b64 = base64.b64encode(
            json.dumps(search, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')
        payload = {
            "Data": search_b64,
            "Sign": calc_signed_api_sign(search_b64),
            "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        }
        resp = client.post("/api/messages/outgoing", json=payload)
        assert resp.status_code == 400


# ─── Incoming ──────────────────────────────────────────────────────────────────

class TestIncoming:
    def test_incoming_valid_202_returns_215_receipt(self, client):
        """Валидная транзакция 202 должна вернуть квиток 215."""
        payload = _make_incoming_payload(202, bg_hash="bg-hash-for-202", chain_guid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        resp = client.post("/api/messages/incoming", json=payload)
        assert resp.status_code == 200

        body = resp.json()
        inner = json.loads(base64.b64decode(body["Data"]).decode('utf-8'))
        assert inner["Count"] == 1
        tx = inner["Transactions"][0]

        # Декодируем Message квитка
        msg = json.loads(base64.b64decode(tx["Data"]).decode('utf-8'))
        assert msg["InfoMessageType"] == 215
        assert msg["SenderBranch"] == "SYSTEM_B"
        assert msg["ReceiverBranch"] == "SYSTEM_A"

    def test_incoming_valid_203_returns_215_receipt(self, client):
        """Валидная транзакция 203 должна вернуть квиток 215."""
        payload = _make_incoming_payload(203, bg_hash="bg-hash-for-203", chain_guid="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        resp = client.post("/api/messages/incoming", json=payload)
        assert resp.status_code == 200
        inner = json.loads(base64.b64decode(resp.json()["Data"]).decode('utf-8'))
        assert inner["Count"] == 1

    def test_incoming_idempotent_second_call_returns_empty(self, client):
        """Повторная отправка той же транзакции возвращает 200 с Count=0."""
        payload = _make_incoming_payload(202, bg_hash="bg-hash-idempotent", chain_guid="cccccccc-cccc-cccc-cccc-cccccccccccc")
        client.post("/api/messages/incoming", json=payload)  # первый раз
        resp = client.post("/api/messages/incoming", json=payload)  # второй раз
        assert resp.status_code == 200
        inner = json.loads(base64.b64decode(resp.json()["Data"]).decode('utf-8'))
        assert inner["Count"] == 0

    def test_incoming_bad_hash_returns_400(self, client):
        """Транзакция с неверным Hash должна отклоняться с 400."""
        payload = _make_incoming_payload(202, bg_hash="bg-bad-hash", chain_guid="dddddddd-dddd-dddd-dddd-dddddddddddd")
        # Подменяем Hash в Data транзакции
        inner_data = json.loads(base64.b64decode(payload["Data"]).decode('utf-8'))
        inner_data["Transactions"][0]["Hash"] = "0" * 64
        new_data_b64 = base64.b64encode(
            json.dumps(inner_data, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')
        payload["Data"] = new_data_b64
        payload["Sign"] = calc_signed_api_sign(new_data_b64)

        resp = client.post("/api/messages/incoming", json=payload)
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_incoming_wrong_transaction_type_returns_400(self, client):
        """TransactionType != 9 должен вернуть 400."""
        payload = _make_incoming_payload(202, bg_hash="bg-wrong-type", chain_guid="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        inner_data = json.loads(base64.b64decode(payload["Data"]).decode('utf-8'))
        inner_data["Transactions"][0]["TransactionType"] = 99
        new_data_b64 = base64.b64encode(
            json.dumps(inner_data, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')
        payload["Data"] = new_data_b64
        payload["Sign"] = calc_signed_api_sign(new_data_b64)

        resp = client.post("/api/messages/incoming", json=payload)
        assert resp.status_code == 400

    def test_incoming_missing_bg_hash_returns_400(self, client):
        """Отсутствие BankGuaranteeHash в payload 202 должно вернуть 400."""
        msg_payload = {"status": "accepted"}  # BankGuaranteeHash отсутствует
        payload_b64 = base64.b64encode(
            json.dumps(msg_payload, separators=(',', ':')).encode('utf-8')
        ).decode('utf-8')
        msg_dict = {
            "Data": payload_b64,
            "SenderBranch": "SYSTEM_A",
            "ReceiverBranch": "SYSTEM_B",
            "InfoMessageType": 202,
            "MessageTime": "2024-05-20T12:00:00Z",
            "ChainGuid": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "PreviousTransactionHash": None,
            "Metadata": None,
        }
        msg_b64 = base64.b64encode(canonical_json_message(msg_dict).encode('utf-8')).decode('utf-8')
        tx_dict = {
            "TransactionType": 9,
            "Data": msg_b64,
            "TransactionTime": "2024-05-20T12:00:00Z",
            "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
            "Metadata": None,
            "TransactionIn": None,
            "TransactionOut": None,
        }
        tx_hash = calc_transaction_hash(tx_dict)
        tx_dict["Hash"] = tx_hash
        tx_dict["Sign"] = calc_transaction_sign(tx_hash)

        txs_data = {"Transactions": [tx_dict], "Count": 1}
        txs_b64 = base64.b64encode(
            canonical_json_transactions_data(txs_data).encode('utf-8')
        ).decode('utf-8')
        incoming = {
            "Data": txs_b64,
            "Sign": calc_signed_api_sign(txs_b64),
            "SignerCert": base64.b64encode(b"SYSTEM_A").decode('utf-8'),
        }

        resp = client.post("/api/messages/incoming", json=incoming)
        assert resp.status_code == 400
        assert "BankGuaranteeHash" in resp.json()["error"]

    def test_incoming_215_receipt_appears_in_outgoing(self, client):
        """Квиток 215 должен появиться в /outgoing после /incoming."""
        payload = _make_incoming_payload(202, bg_hash="bg-e2e-outgoing", chain_guid="12345678-1234-1234-1234-123456789012")
        resp = client.post("/api/messages/incoming", json=payload)
        assert resp.status_code == 200

        outgoing_payload = _make_outgoing_payload("2024-01-01T00:00:00Z", "2030-12-31T23:59:59Z")
        out_resp = client.post("/api/messages/outgoing", json=outgoing_payload)
        assert out_resp.status_code == 200

        inner = json.loads(base64.b64decode(out_resp.json()["Data"]).decode('utf-8'))
        msg_types = []
        for tx in inner["Transactions"]:
            msg = json.loads(base64.b64decode(tx["Data"]).decode('utf-8'))
            msg_types.append(msg["InfoMessageType"])
        assert 215 in msg_types
