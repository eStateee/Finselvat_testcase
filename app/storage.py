import sqlite3
import os
from typing import Tuple, List, Dict

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "app.db"))

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    try:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    hash TEXT PRIMARY KEY,
                    transaction_type INTEGER NOT NULL,
                    transaction_time TEXT NOT NULL,
                    data_base64 TEXT NOT NULL,
                    sign_base64 TEXT NOT NULL,
                    signer_cert_base64 TEXT NOT NULL,
                    metadata TEXT,
                    transaction_in TEXT,
                    transaction_out TEXT,
                    receiver_branch TEXT NOT NULL,
                    info_message_type INTEGER NOT NULL,
                    chain_guid TEXT NOT NULL,
                    bank_guarantee_hash TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_receiver_branch ON transactions (receiver_branch)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_transaction_time ON transactions (transaction_time)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_receiver_time ON transactions (receiver_branch, transaction_time)')
    finally:
        conn.close()

def insert_transaction_if_absent(row: dict) -> bool:
    conn = get_connection()
    try:
        with conn:
            conn.execute('''
                INSERT INTO transactions (
                    hash, transaction_type, transaction_time, data_base64,
                    sign_base64, signer_cert_base64, metadata, transaction_in,
                    transaction_out, receiver_branch, info_message_type,
                    chain_guid, bank_guarantee_hash
                ) VALUES (
                    :hash, :transaction_type, :transaction_time, :data_base64,
                    :sign_base64, :signer_cert_base64, :metadata, :transaction_in,
                    :transaction_out, :receiver_branch, :info_message_type,
                    :chain_guid, :bank_guarantee_hash
                )
            ''', row)
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def query_outgoing(start_date: str, end_date: str, limit: int, offset: int) -> Tuple[List[dict], int]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT COUNT(*) FROM transactions
            WHERE receiver_branch = 'SYSTEM_A'
              AND transaction_time >= ?
              AND transaction_time <= ?
        ''', (start_date, end_date))
        count_total = cur.fetchone()[0]

        cur.execute('''
            SELECT hash as Hash,
                   transaction_type as TransactionType,
                   transaction_time as TransactionTime,
                   data_base64 as Data,
                   sign_base64 as Sign,
                   signer_cert_base64 as SignerCert,
                   metadata as Metadata,
                   transaction_in as TransactionIn,
                   transaction_out as TransactionOut
            FROM transactions
            WHERE receiver_branch = 'SYSTEM_A'
              AND transaction_time >= ?
              AND transaction_time <= ?
            ORDER BY transaction_time ASC, hash ASC
            LIMIT ? OFFSET ?
        ''', (start_date, end_date, limit, offset))
        
        rows = [dict(r) for r in cur.fetchall()]
        return rows, count_total
    finally:
        conn.close()

def get_transaction_count() -> int:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM transactions')
        return cur.fetchone()[0]
    finally:
        conn.close()
