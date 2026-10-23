import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finance.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Accounts / Wallets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'bank', -- 'cash', 'bank', 'ewallet', 'saving', 'credit'
            initial_balance REAL NOT NULL DEFAULT 0,
            current_balance REAL NOT NULL DEFAULT 0,
            icon TEXT DEFAULT 'wallet',
            color TEXT DEFAULT '#3b82f6',
            account_number TEXT DEFAULT '',
            note TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Family Members
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT 'Thành viên', -- 'Bố/Chồng', 'Mẹ/Vợ', 'Con cái', 'Chung', 'Khác'
            avatar_color TEXT DEFAULT '#10b981',
            note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Categories
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'income', 'expense'
            icon TEXT DEFAULT 'tag',
            color TEXT DEFAULT '#64748b',
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Transactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL, -- 'income', 'expense', 'transfer'
            amount REAL NOT NULL,
            transaction_date TEXT NOT NULL, -- YYYY-MM-DD
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE,
            to_account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE, -- only for transfer
            member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
            note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Monthly Budgets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
            month INTEGER NOT NULL, -- 1-12
            year INTEGER NOT NULL,
            amount REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(category_id, month, year)
        )
    ''')

    # 6. Savings Goals
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL NOT NULL DEFAULT 0,
            deadline TEXT DEFAULT '', -- YYYY-MM-DD
            category TEXT DEFAULT 'Chung',
            color TEXT DEFAULT '#6366f1',
            status TEXT DEFAULT 'in_progress', -- 'in_progress', 'completed'
            note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

def recalculate_all_balances():
    """Recalculate current_balance for all accounts from initial balance + all transactions."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Reset to initial balance
    cursor.execute("UPDATE accounts SET current_balance = initial_balance")

    # Incomes
    cursor.execute('''
        SELECT account_id, SUM(amount) as total
        FROM transactions
        WHERE type = 'income' AND account_id IS NOT NULL
        GROUP BY account_id
    ''')
    for row in cursor.fetchall():
        cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ?", (row['total'], row['account_id']))

    # Expenses
    cursor.execute('''
        SELECT account_id, SUM(amount) as total
        FROM transactions
        WHERE type = 'expense' AND account_id IS NOT NULL
        GROUP BY account_id
    ''')
    for row in cursor.fetchall():
        cursor.execute("UPDATE accounts SET current_balance = current_balance - ? WHERE id = ?", (row['total'], row['account_id']))

    # Transfers Out
    cursor.execute('''
        SELECT account_id, SUM(amount) as total
        FROM transactions
        WHERE type = 'transfer' AND account_id IS NOT NULL
        GROUP BY account_id
    ''')
    for row in cursor.fetchall():
        cursor.execute("UPDATE accounts SET current_balance = current_balance - ? WHERE id = ?", (row['total'], row['account_id']))

    # Transfers In
    cursor.execute('''
        SELECT to_account_id, SUM(amount) as total
        FROM transactions
        WHERE type = 'transfer' AND to_account_id IS NOT NULL
        GROUP BY to_account_id
    ''')
    for row in cursor.fetchall():
        cursor.execute("UPDATE accounts SET current_balance = current_balance + ? WHERE id = ?", (row['total'], row['to_account_id']))

    conn.commit()
    conn.close()
