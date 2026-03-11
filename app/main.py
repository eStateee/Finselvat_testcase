from fastapi import FastAPI, Request, status, Body
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import json
import base64
import uuid
import os

from app.storage import init_db, get_transaction_count, insert_transaction_if_absent, query_outgoing
from app.crypto import canonical_json_message, calc_transaction_hash, calc_transaction_sign, canonical_json_transactions_data, calc_signed_api_sign
from app.schemas import SignedApiData, TransactionsData, SearchRequest, Transaction, Message

@asynccontextmanager
async def lifespan(app: FastAPI):
    # init DB
    init_db()
    
    # seed 201 transaction if DB empty
    if get_transaction_count() == 0:
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "guarantee_201_payload.json")
        with open(fixture_path, 'r', encoding='utf-8') as f:
            payload_json = json.load(f)
            
        payload_b64 = base64.b64encode(json.dumps(payload_json, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('utf-8')
        
        msg_dict = {
            "Data": payload_b64,
            "SenderBranch": "SYSTEM_B",
            "ReceiverBranch": "SYSTEM_A",
            "InfoMessageType": 201,
            "MessageTime": "2024-05-20T10:00:00Z",
            "ChainGuid": str(uuid.uuid4()),
            "PreviousTransactionHash": None,
            "Metadata": None
        }
        
        msg_b64 = base64.b64encode(canonical_json_message(msg_dict).encode('utf-8')).decode('utf-8')
        
        tx_dict = {
            "TransactionType": 9,
            "Data": msg_b64,
            "TransactionTime": "2024-05-20T10:00:00Z",
            "SignerCert": base64.b64encode(b"SYSTEM_B").decode('utf-8'),
            "Metadata": None,
            "TransactionIn": None,
            "TransactionOut": None
        }
        
        tx_hash = calc_transaction_hash(tx_dict)
        tx_sign = calc_transaction_sign(tx_hash)
        
        row = {
            "hash": tx_hash,
            "transaction_type": 9,
            "transaction_time": "2024-05-20T10:00:00Z",
            "data_base64": msg_b64,
            "sign_base64": tx_sign,
            "signer_cert_base64": tx_dict["SignerCert"],
            "metadata": None,
            "transaction_in": None,
            "transaction_out": None,
            "receiver_branch": "SYSTEM_A",
            "info_message_type": 201,
            "chain_guid": msg_dict["ChainGuid"],
            "bank_guarantee_hash": payload_json.get("BankGuaranteeHash")
        }
        
        insert_transaction_if_absent(row)
        
    yield

app = FastAPI(title="System B API", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Validation error: " + str(exc.errors())}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(status_code=404, content={"error": "Not Found"})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": exc.detail}
    )

@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": str(exc)}
    )

@app.exception_handler(json.JSONDecodeError)
async def json_decode_exception_handler(request: Request, exc: json.JSONDecodeError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid JSON payload"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import logging
    logging.error(f"Unhandled exception: {exc}")
    # Following user global rules: no try catch except on asynchronous requests!!!
    # But here we are at the top level route error handler framework, to catch 500s 
    # and provide them consistently.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error"}
    )

@app.get("/api/health")
async def health_check():
    return PlainTextResponse(content="OK", status_code=200)

@app.post("/api/messages/outgoing")
async def messages_outgoing(payload: SignedApiData = Body(...)):
    try:
        data_json = base64.b64decode(payload.Data, validate=True).decode('utf-8')
        search_request_dict = json.loads(data_json)
        search_req = SearchRequest(**search_request_dict)
    except Exception as e:
        # Standard validation error return per spec Task 2 -> 400 with "error"
        # Since we are already validating SearchRequest using pydantic manually here
        # we can just raise a ValueError which the exception_handler intercepts.
        raise ValueError(f"Invalid Data payload: {str(e)}")
        
    start_date_str = search_req.StartDate.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_date_str = search_req.EndDate.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    rows, count_total = query_outgoing(
        start_date=start_date_str,
        end_date=end_date_str,
        limit=search_req.Limit,
        offset=search_req.Offset
    )
    
    # We should return transactions with properly parsed JSON logic
    # In 'rows', data_base64 corresponds to Data, etc. but TransactionIn might be NULL etc.
    # Luckily our query maps precisely to the Transaction pydantic model.
    transactions = [Transaction(**r).model_dump(mode='json') for r in rows]
    tx_data_dict = {"Transactions": transactions, "Count": count_total}
    
    canonical_tx_data = canonical_json_transactions_data(tx_data_dict)
    data_b64 = base64.b64encode(canonical_tx_data.encode('utf-8')).decode('utf-8')
    signer_cert_b64 = base64.b64encode(b"SYSTEM_B").decode('utf-8')
    sign_b64 = calc_signed_api_sign(data_b64)
    
    return JSONResponse(status_code=200, content={
        "Data": data_b64,
        "Sign": sign_b64,
        "SignerCert": signer_cert_b64
    })

@app.post("/api/messages/incoming")
async def messages_incoming(payload: SignedApiData = Body(...)):
    try:
        data_json = base64.b64decode(payload.Data, validate=True).decode('utf-8')
        txs_data_dict = json.loads(data_json)
        txs_data = TransactionsData(**txs_data_dict)
    except Exception as e:
        raise ValueError(f"Invalid Data payload: {str(e)}")
        
    receipts = []
    
    from datetime import datetime
    
    for t in txs_data.Transactions:
        if t.TransactionType != 9:
            raise ValueError("Invalid TransactionType: must be 9")
        if not t.Sign:
            raise ValueError("Empty Sign in Transaction")
            
        t_dict = t.model_dump(mode='json')
        calc_hash = calc_transaction_hash(t_dict)
        if calc_hash != t.Hash:
            raise ValueError("Invalid Hash in Transaction")
            
        try:
            msg_json = base64.b64decode(t.Data, validate=True).decode('utf-8')
            msg_dict = json.loads(msg_json)
            msg = Message(**msg_dict)
        except Exception as e:
            raise ValueError(f"Invalid Message payload: {str(e)}")
            
        if msg.SenderBranch != "SYSTEM_A":
            raise ValueError("Invalid SenderBranch, expected SYSTEM_A")
        if msg.ReceiverBranch != "SYSTEM_B":
            raise ValueError("Invalid ReceiverBranch, expected SYSTEM_B")
        if msg.InfoMessageType not in (202, 203, 215):
            raise ValueError("Invalid InfoMessageType, expected 202, 203 or 215")
            
        bg_hash = None
        if msg.InfoMessageType != 215:
            try:
                payload_json = base64.b64decode(msg.Data, validate=True).decode('utf-8')
                payload_dict = json.loads(payload_json)
                bg_hash = payload_dict.get("BankGuaranteeHash")
                if not bg_hash:
                    raise ValueError("BankGuaranteeHash missing in Message payload")
            except Exception as e:
                raise ValueError(f"Invalid BankGuaranteeHash: {str(e)}")
                
        row = {
            "hash": t.Hash,
            "transaction_type": t.TransactionType,
            "transaction_time": t.TransactionTime.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "data_base64": t.Data,
            "sign_base64": t.Sign,
            "signer_cert_base64": t.SignerCert,
            "metadata": t.Metadata,
            "transaction_in": t.TransactionIn,
            "transaction_out": t.TransactionOut,
            "receiver_branch": msg.ReceiverBranch,
            "info_message_type": msg.InfoMessageType,
            "chain_guid": msg.ChainGuid,
            "bank_guarantee_hash": bg_hash
        }
        
        is_new = insert_transaction_if_absent(row)
        
        if is_new and msg.InfoMessageType in (202, 203):
            # Generate 215
            receipt_payload = {"BankGuaranteeHash": bg_hash}
            receipt_payload_b64 = base64.b64encode(json.dumps(receipt_payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).decode('utf-8')
            
            now_utc = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            
            rec_msg_dict = {
                "Data": receipt_payload_b64,
                "SenderBranch": "SYSTEM_B",
                "ReceiverBranch": "SYSTEM_A",
                "InfoMessageType": 215,
                "MessageTime": now_utc,
                "ChainGuid": msg.ChainGuid,
                "PreviousTransactionHash": t.Hash,
                "Metadata": None
            }
            
            rec_msg_b64 = base64.b64encode(canonical_json_message(rec_msg_dict).encode('utf-8')).decode('utf-8')
            
            rec_tx_dict = {
                "TransactionType": 9,
                "Data": rec_msg_b64,
                "TransactionTime": now_utc,
                "SignerCert": base64.b64encode(b"SYSTEM_B").decode('utf-8'),
                "Metadata": None,
                "TransactionIn": None,
                "TransactionOut": None
            }
            
            rec_tx_hash = calc_transaction_hash(rec_tx_dict)
            rec_tx_sign = calc_transaction_sign(rec_tx_hash)
            
            rec_tx_dict["Hash"] = rec_tx_hash
            rec_tx_dict["Sign"] = rec_tx_sign
            
            rec_row = {
                "hash": rec_tx_hash,
                "transaction_type": 9,
                "transaction_time": now_utc,
                "data_base64": rec_msg_b64,
                "sign_base64": rec_tx_sign,
                "signer_cert_base64": rec_tx_dict["SignerCert"],
                "metadata": None,
                "transaction_in": None,
                "transaction_out": None,
                "receiver_branch": "SYSTEM_A",
                "info_message_type": 215,
                "chain_guid": msg.ChainGuid,
                "bank_guarantee_hash": bg_hash
            }
            
            insert_transaction_if_absent(rec_row)
            receipts.append(rec_tx_dict)

    tx_data_dict = {"Transactions": receipts, "Count": len(receipts)}
    canonical_tx_data = canonical_json_transactions_data(tx_data_dict)
    data_b64 = base64.b64encode(canonical_tx_data.encode('utf-8')).decode('utf-8')
    signer_cert_b64 = base64.b64encode(b"SYSTEM_B").decode('utf-8')
    sign_b64 = calc_signed_api_sign(data_b64)

    return JSONResponse(status_code=200, content={
        "Data": data_b64,
        "Sign": sign_b64,
        "SignerCert": signer_cert_b64
    })
