import os
import sys

# Ensure UTF-8 output on Windows console
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash
from database import init_db, get_db_connection, recalculate_all_balances
from sample_data import seed_sample_data
from export_service import export_transactions_to_excel, export_transactions_to_csv

app = Flask(__name__)
app.secret_key = 'taichinh-giadinh-secret-key-2026'

# Custom template filters for Vietnamese currency and dates
@app.template_filter('currency')
def currency_filter(value):
    try:
        val = float(value or 0)
        return f"{val:,.0f}".replace(",", ".") + " ₫"
    except (ValueError, TypeError):
        return "0 ₫"

@app.template_filter('format_date')
def format_date_filter(val):
    if not val:
        return ""
    try:
        dt = datetime.strptime(str(val), '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except Exception:
        return str(val)

# Helper to get current month/year
def get_current_period():
    now = datetime.now()
    return now.month, now.year

# ----------------- WEB ROUTES ----------------- #

@app.route('/')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    cur_m, cur_y = get_current_period()
    cur_m_str = f"{cur_y}-{cur_m:02d}"

    # Previous month string for comparison
    prev_date = datetime.now().replace(day=1) - timedelta(days=1)
    prev_m_str = f"{prev_date.year}-{prev_date.month:02d}"

    # 1. Total Net Worth (All active accounts)
    cursor.execute("SELECT SUM(current_balance) as total_wealth FROM accounts WHERE is_active = 1")
    total_wealth = cursor.fetchone()['total_wealth'] or 0

    # 2. Total Incomes & Expenses for current month
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as month_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as month_expense
        FROM transactions
        WHERE strftime('%Y-%m', transaction_date) = ?
    ''', (cur_m_str,))
    cur_month_stat = cursor.fetchone()
    month_income = cur_month_stat['month_income'] or 0
    month_expense = cur_month_stat['month_expense'] or 0
    month_balance = month_income - month_expense
    savings_rate = (month_balance / month_income * 100) if month_income > 0 else 0

    # 3. Previous month stat for comparison
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as prev_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as prev_expense
        FROM transactions
        WHERE strftime('%Y-%m', transaction_date) = ?
    ''', (prev_m_str,))
    prev_stat = cursor.fetchone()
    prev_income = prev_stat['prev_income'] or 0
    prev_expense = prev_stat['prev_expense'] or 0

    # 4. Accounts summary
    cursor.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY current_balance DESC")
    accounts = cursor.fetchall()

    # 5. Recent 8 transactions
    cursor.execute('''
        SELECT 
            t.*,
            c.name as category_name, c.icon as category_icon, c.color as category_color,
            a.name as account_name,
            ta.name as to_account_name,
            m.name as member_name, m.avatar_color as member_color
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        LEFT JOIN members m ON t.member_id = m.id
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT 8
    ''')
    recent_transactions = cursor.fetchall()

    # 6. Budgets for current month with spent amounts
    cursor.execute('''
        SELECT 
            b.*,
            c.name as category_name, c.icon as category_icon, c.color as category_color,
            COALESCE(spent.total_spent, 0) as total_spent
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        LEFT JOIN (
            SELECT category_id, SUM(amount) as total_spent
            FROM transactions
            WHERE type = 'expense' AND strftime('%Y-%m', transaction_date) = ?
            GROUP BY category_id
        ) spent ON b.category_id = spent.category_id
        WHERE b.month = ? AND b.year = ?
        ORDER BY b.amount DESC
        LIMIT 5
    ''', (cur_m_str, cur_m, cur_y))
    budgets = cursor.fetchall()

    # 7. Goals in progress
    cursor.execute("SELECT * FROM goals WHERE status = 'in_progress' ORDER BY target_amount DESC LIMIT 4")
    goals = cursor.fetchall()

    # Categories for quick add
    cursor.execute("SELECT * FROM categories ORDER BY type DESC, name ASC")
    categories = cursor.fetchall()

    # Members for quick add
    cursor.execute("SELECT * FROM members ORDER BY name ASC")
    members = cursor.fetchall()

    conn.close()

    return render_template(
        'index.html',
        total_wealth=total_wealth,
        month_income=month_income,
        month_expense=month_expense,
        month_balance=month_balance,
        savings_rate=savings_rate,
        prev_income=prev_income,
        prev_expense=prev_expense,
        accounts=accounts,
        recent_transactions=recent_transactions,
        budgets=budgets,
        goals=goals,
        categories=categories,
        members=members,
        cur_m=cur_m,
        cur_y=cur_y
    )

@app.route('/transactions')
def transactions():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query params
    page = int(request.args.get('page', 1))
    per_page = 20
    offset = (page - 1) * per_page

    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    tx_type = request.args.get('type', '')
    account_id = request.args.get('account_id', '')
    category_id = request.args.get('category_id', '')
    member_id = request.args.get('member_id', '')
    search = request.args.get('search', '').strip()

    where_clauses = ["1=1"]
    params = []

    if start_date:
        where_clauses.append("t.transaction_date >= ?")
        params.append(start_date)
    if end_date:
        where_clauses.append("t.transaction_date <= ?")
        params.append(end_date)
    if tx_type:
        where_clauses.append("t.type = ?")
        params.append(tx_type)
    if account_id:
        where_clauses.append("(t.account_id = ? OR t.to_account_id = ?)")
        params.extend([account_id, account_id])
    if category_id:
        where_clauses.append("t.category_id = ?")
        params.append(category_id)
    if member_id:
        where_clauses.append("t.member_id = ?")
        params.append(member_id)
    if search:
        where_clauses.append("(t.note LIKE ? OR c.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_sql = " AND ".join(where_clauses)

    # Count total
    cursor.execute(f'''
        SELECT COUNT(*) as total_count,
               SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END) as sum_income,
               SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END) as sum_expense
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE {where_sql}
    ''', params)
    stat = cursor.fetchone()
    total_count = stat['total_count'] or 0
    sum_income = stat['sum_income'] or 0
    sum_expense = stat['sum_expense'] or 0
    total_pages = max(1, (total_count + per_page - 1) // per_page)

    # Fetch rows
    fetch_params = list(params) + [per_page, offset]
    cursor.execute(f'''
        SELECT 
            t.*,
            c.name as category_name, c.icon as category_icon, c.color as category_color,
            a.name as account_name,
            ta.name as to_account_name,
            m.name as member_name, m.avatar_color as member_color
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        LEFT JOIN members m ON t.member_id = m.id
        WHERE {where_sql}
        ORDER BY t.transaction_date DESC, t.id DESC
        LIMIT ? OFFSET ?
    ''', fetch_params)
    transactions_list = cursor.fetchall()

    # Dropdown lookups
    cursor.execute("SELECT * FROM categories ORDER BY type DESC, name ASC")
    categories = cursor.fetchall()
    cursor.execute("SELECT * FROM accounts WHERE is_active = 1 ORDER BY name ASC")
    accounts = cursor.fetchall()
    cursor.execute("SELECT * FROM members ORDER BY name ASC")
    members = cursor.fetchall()

    conn.close()

    return render_template(
        'transactions.html',
        transactions=transactions_list,
        categories=categories,
        accounts=accounts,
        members=members,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        sum_income=sum_income,
        sum_expense=sum_expense,
        start_date=start_date,
        end_date=end_date,
        tx_type=tx_type,
        account_id=account_id,
        category_id=category_id,
        member_id=member_id,
        search=search,
        today=datetime.now().strftime('%Y-%m-%d')
    )

@app.route('/reports')
def reports():
    conn = get_db_connection()
    cursor = conn.cursor()

    cur_m, cur_y = get_current_period()
    selected_month = int(request.args.get('month', cur_m))
    selected_year = int(request.args.get('year', cur_y))
    month_str = f"{selected_year}-{selected_month:02d}"

    # Summary of this month
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as total_income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as total_expense
        FROM transactions
        WHERE strftime('%Y-%m', transaction_date) = ?
    ''', (month_str,))
    summary = cursor.fetchone()
    total_income = summary['total_income'] or 0
    total_expense = summary['total_expense'] or 0
    net_savings = total_income - total_expense
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0

    # Expense breakdown by category
    cursor.execute('''
        SELECT 
            c.id, c.name, c.color, c.icon,
            SUM(t.amount) as amount,
            ROUND(SUM(t.amount) * 100.0 / NULLIF((SELECT SUM(amount) FROM transactions WHERE type='expense' AND strftime('%Y-%m', transaction_date) = ?), 0), 1) as percentage,
            b.amount as budget_amount
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        LEFT JOIN budgets b ON b.category_id = c.id AND b.month = ? AND b.year = ?
        WHERE t.type = 'expense' AND strftime('%Y-%m', transaction_date) = ?
        GROUP BY c.id
        ORDER BY amount DESC
    ''', (month_str, selected_month, selected_year, month_str))
    expense_by_category = cursor.fetchall()

    # Income breakdown by category
    cursor.execute('''
        SELECT 
            c.id, c.name, c.color, c.icon,
            SUM(t.amount) as amount,
            ROUND(SUM(t.amount) * 100.0 / NULLIF((SELECT SUM(amount) FROM transactions WHERE type='income' AND strftime('%Y-%m', transaction_date) = ?), 0), 1) as percentage
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'income' AND strftime('%Y-%m', transaction_date) = ?
        GROUP BY c.id
        ORDER BY amount DESC
    ''', (month_str, month_str))
    income_by_category = cursor.fetchall()

    # Member breakdown for this month
    cursor.execute('''
        SELECT 
            m.id, m.name, m.role, m.avatar_color,
            SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END) as member_expense,
            SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END) as member_income
        FROM members m
        LEFT JOIN transactions t ON t.member_id = m.id AND strftime('%Y-%m', t.transaction_date) = ?
        GROUP BY m.id
        ORDER BY member_expense DESC
    ''', (month_str,))
    member_stats = cursor.fetchall()

    conn.close()

    return render_template(
        'reports.html',
        selected_month=selected_month,
        selected_year=selected_year,
        total_income=total_income,
        total_expense=total_expense,
        net_savings=net_savings,
        savings_rate=savings_rate,
        expense_by_category=expense_by_category,
        income_by_category=income_by_category,
        member_stats=member_stats
    )

@app.route('/accounts')
def accounts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts ORDER BY is_active DESC, type ASC, name ASC")
    accounts_list = cursor.fetchall()

    # Calculate total balance
    total_balance = sum(a['current_balance'] for a in accounts_list if a['is_active'])

    conn.close()
    return render_template('accounts.html', accounts=accounts_list, total_balance=total_balance)

@app.route('/budgets')
def budgets():
    conn = get_db_connection()
    cursor = conn.cursor()

    cur_m, cur_y = get_current_period()
    month = int(request.args.get('month', cur_m))
    year = int(request.args.get('year', cur_y))
    month_str = f"{year}-{month:02d}"

    cursor.execute('''
        SELECT 
            b.*,
            c.name as category_name, c.color as category_color, c.icon as category_icon,
            COALESCE(spent.total_spent, 0) as total_spent
        FROM budgets b
        JOIN categories c ON b.category_id = c.id
        LEFT JOIN (
            SELECT category_id, SUM(amount) as total_spent
            FROM transactions
            WHERE type = 'expense' AND strftime('%Y-%m', transaction_date) = ?
            GROUP BY category_id
        ) spent ON b.category_id = spent.category_id
        WHERE b.month = ? AND b.year = ?
        ORDER BY b.amount DESC
    ''', (month_str, month, year))
    budgets_list = cursor.fetchall()

    # Categories without budget for modal dropdown
    cursor.execute('''
        SELECT * FROM categories 
        WHERE type = 'expense' 
        AND id NOT IN (SELECT category_id FROM budgets WHERE month = ? AND year = ?)
        ORDER BY name ASC
    ''', (month, year))
    available_categories = cursor.fetchall()

    total_budget = sum(b['amount'] for b in budgets_list)
    total_spent = sum(b['total_spent'] for b in budgets_list)

    conn.close()
    return render_template(
        'budgets.html',
        budgets=budgets_list,
        available_categories=available_categories,
        month=month,
        year=year,
        total_budget=total_budget,
        total_spent=total_spent
    )

@app.route('/goals')
def goals():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals ORDER BY status ASC, deadline ASC")
    goals_list = cursor.fetchall()

    # Accounts for deposit modal
    cursor.execute("SELECT * FROM accounts WHERE is_active = 1 AND current_balance > 0")
    accounts = cursor.fetchall()

    conn.close()
    return render_template('goals.html', goals=goals_list, accounts=accounts)

@app.route('/members')
def members():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT 
            m.*,
            COALESCE(SUM(CASE WHEN t.type = 'income' THEN t.amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN t.type = 'expense' THEN t.amount ELSE 0 END), 0) as total_expense,
            COUNT(t.id) as tx_count
        FROM members m
        LEFT JOIN transactions t ON m.id = t.member_id
        GROUP BY m.id
        ORDER BY total_income DESC, m.name ASC
    ''')
    members_list = cursor.fetchall()

    conn.close()
    return render_template('members.html', members=members_list)

@app.route('/categories')
def categories():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT c.*, COUNT(t.id) as tx_count, COALESCE(SUM(t.amount), 0) as total_amount
        FROM categories c
        LEFT JOIN transactions t ON c.id = t.category_id
        GROUP BY c.id
        ORDER BY c.type DESC, total_amount DESC
    ''')
    categories_list = cursor.fetchall()

    conn.close()
    return render_template('categories.html', categories=categories_list)


# ----------------- REST API / ACTIONS ----------------- #

@app.route('/api/transactions', methods=['POST'])
def add_transaction():
    try:
        data = request.form if request.form else request.get_json()
        tx_type = data.get('type')
        amount = float(data.get('amount') or 0)
        transaction_date = data.get('transaction_date') or datetime.now().strftime('%Y-%m-%d')
        account_id = data.get('account_id')
        to_account_id = data.get('to_account_id') if tx_type == 'transfer' else None
        category_id = data.get('category_id') if tx_type != 'transfer' else None
        member_id = data.get('member_id')
        note = data.get('note', '').strip()

        if amount <= 0:
            return jsonify({'success': False, 'message': 'Số tiền phải lớn hơn 0'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO transactions (type, amount, transaction_date, category_id, account_id, to_account_id, member_id, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tx_type, amount, transaction_date, category_id, account_id, to_account_id, member_id, note))
        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Giao dịch đã được lưu thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:tx_id>', methods=['GET'])
def get_transaction(tx_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    tx = cursor.fetchone()
    conn.close()
    if tx:
        return jsonify({'success': True, 'data': dict(tx)})
    return jsonify({'success': False, 'message': 'Không tìm thấy giao dịch'}), 404

@app.route('/api/transactions/<int:tx_id>', methods=['POST', 'PUT'])
def update_transaction(tx_id):
    try:
        data = request.form if request.form else request.get_json()
        tx_type = data.get('type')
        amount = float(data.get('amount') or 0)
        transaction_date = data.get('transaction_date')
        account_id = data.get('account_id')
        to_account_id = data.get('to_account_id') if tx_type == 'transfer' else None
        category_id = data.get('category_id') if tx_type != 'transfer' else None
        member_id = data.get('member_id')
        note = data.get('note', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE transactions
            SET type = ?, amount = ?, transaction_date = ?, category_id = ?, 
                account_id = ?, to_account_id = ?, member_id = ?, note = ?
            WHERE id = ?
        ''', (tx_type, amount, transaction_date, category_id, account_id, to_account_id, member_id, note, tx_id))
        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Cập nhật giao dịch thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/<int:tx_id>/delete', methods=['POST', 'DELETE'])
def delete_transaction(tx_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Đã xóa giao dịch!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Accounts API
@app.route('/api/accounts', methods=['POST'])
def create_account():
    try:
        data = request.form if request.form else request.get_json()
        name = data.get('name', '').strip()
        acc_type = data.get('type', 'bank')
        initial_balance = float(data.get('initial_balance') or 0)
        color = data.get('color', '#3b82f6')
        icon = data.get('icon', 'wallet')
        account_number = data.get('account_number', '').strip()
        note = data.get('note', '').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Tên tài khoản không được để trống'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO accounts (name, type, initial_balance, current_balance, color, icon, account_number, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, acc_type, initial_balance, initial_balance, color, icon, account_number, note))
        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Thêm tài khoản thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accounts/<int:acc_id>', methods=['POST', 'PUT'])
def update_account(acc_id):
    try:
        data = request.form if request.form else request.get_json()
        name = data.get('name', '').strip()
        acc_type = data.get('type', 'bank')
        initial_balance = float(data.get('initial_balance') or 0)
        color = data.get('color', '#3b82f6')
        icon = data.get('icon', 'wallet')
        account_number = data.get('account_number', '').strip()
        note = data.get('note', '').strip()
        is_active = int(data.get('is_active', 1))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE accounts
            SET name = ?, type = ?, initial_balance = ?, color = ?, icon = ?, account_number = ?, note = ?, is_active = ?
            WHERE id = ?
        ''', (name, acc_type, initial_balance, color, icon, account_number, note, is_active, acc_id))
        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Cập nhật tài khoản thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accounts/<int:acc_id>/delete', methods=['POST', 'DELETE'])
def delete_account(acc_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Check if there are transactions
        cursor.execute("SELECT COUNT(*) as cnt FROM transactions WHERE account_id = ? OR to_account_id = ?", (acc_id, acc_id))
        cnt = cursor.fetchone()['cnt']
        if cnt > 0:
            # Soft delete (deactivate)
            cursor.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (acc_id,))
        else:
            cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Đã đóng / xóa tài khoản!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Members API
@app.route('/api/members', methods=['POST'])
def add_member():
    try:
        data = request.form if request.form else request.get_json()
        name = data.get('name', '').strip()
        role = data.get('role', 'Thành viên')
        avatar_color = data.get('avatar_color', '#10b981')
        note = data.get('note', '').strip()

        if not name:
            return jsonify({'success': False, 'message': 'Tên thành viên không được để trống'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO members (name, role, avatar_color, note)
            VALUES (?, ?, ?, ?)
        ''', (name, role, avatar_color, note))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Thêm thành viên thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/members/<int:member_id>/delete', methods=['POST', 'DELETE'])
def delete_member(member_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM members WHERE id = ?", (member_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Đã xóa thành viên!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Categories API
@app.route('/api/categories', methods=['POST'])
def add_category():
    try:
        data = request.form if request.form else request.get_json()
        name = data.get('name', '').strip()
        cat_type = data.get('type', 'expense')
        icon = data.get('icon', 'tag')
        color = data.get('color', '#6366f1')

        if not name:
            return jsonify({'success': False, 'message': 'Tên danh mục không được để trống'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO categories (name, type, icon, color)
            VALUES (?, ?, ?, ?)
        ''', (name, cat_type, icon, color))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Thêm danh mục thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/categories/<int:cat_id>/delete', methods=['POST', 'DELETE'])
def delete_category(cat_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Đã xóa danh mục!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Budgets API
@app.route('/api/budgets', methods=['POST'])
def save_budget():
    try:
        data = request.form if request.form else request.get_json()
        category_id = int(data.get('category_id'))
        month = int(data.get('month'))
        year = int(data.get('year'))
        amount = float(data.get('amount') or 0)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO budgets (category_id, month, year, amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(category_id, month, year) DO UPDATE SET amount = excluded.amount
        ''', (category_id, month, year, amount))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Lưu ngân sách thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/budgets/<int:b_id>/delete', methods=['POST', 'DELETE'])
def delete_budget(b_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM budgets WHERE id = ?", (b_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Đã xóa ngân sách!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Goals API
@app.route('/api/goals', methods=['POST'])
def add_goal():
    try:
        data = request.form if request.form else request.get_json()
        name = data.get('name', '').strip()
        target_amount = float(data.get('target_amount') or 0)
        current_amount = float(data.get('current_amount') or 0)
        deadline = data.get('deadline', '')
        category = data.get('category', 'Chung')
        color = data.get('color', '#6366f1')
        note = data.get('note', '')

        if not name or target_amount <= 0:
            return jsonify({'success': False, 'message': 'Vui lòng nhập tên mục tiêu và số tiền hợp lệ'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO goals (name, target_amount, current_amount, deadline, category, color, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, target_amount, current_amount, deadline, category, color, note))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Thêm mục tiêu thành công!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/goals/<int:goal_id>/deposit', methods=['POST'])
def deposit_goal(goal_id):
    try:
        data = request.form if request.form else request.get_json()
        amount = float(data.get('amount') or 0)
        account_id = data.get('account_id')

        if amount <= 0:
            return jsonify({'success': False, 'message': 'Số tiền nạp phải lớn hơn 0'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Update goal
        cursor.execute("UPDATE goals SET current_amount = current_amount + ? WHERE id = ?", (amount, goal_id))
        
        # Check if completed
        cursor.execute("SELECT current_amount, target_amount FROM goals WHERE id = ?", (goal_id,))
        g = cursor.fetchone()
        if g['current_amount'] >= g['target_amount']:
            cursor.execute("UPDATE goals SET status = 'completed' WHERE id = ?", (goal_id,))

        # Optionally deduct from account via an expense or transfer
        if account_id:
            cursor.execute('''
                INSERT INTO transactions (type, amount, transaction_date, account_id, note)
                VALUES ('expense', ?, ?, ?, ?)
            ''', (amount, datetime.now().strftime('%Y-%m-%d'), account_id, f"Tích lũy quỹ: Mục tiêu #{goal_id}"))

        conn.commit()
        conn.close()

        recalculate_all_balances()
        return jsonify({'success': True, 'message': 'Đã nạp tiền tích lũy vào mục tiêu!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/goals/<int:goal_id>/delete', methods=['POST', 'DELETE'])
def delete_goal(goal_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Đã xóa mục tiêu!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ----------------- CHART DATA APIS ----------------- #

@app.route('/api/charts/cashflow')
def chart_cashflow():
    """Returns 6-month monthly income vs expense."""
    conn = get_db_connection()
    cursor = conn.cursor()

    labels = []
    incomes = []
    expenses = []

    now = datetime.now()
    for i in range(5, -1, -1):
        # Calculate month
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1

        m_str = f"{year}-{month:02d}"
        labels.append(f"T{month}/{year}")

        cursor.execute('''
            SELECT 
                SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as inc,
                SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as exp
            FROM transactions
            WHERE strftime('%Y-%m', transaction_date) = ?
        ''', (m_str,))
        row = cursor.fetchone()
        incomes.append(row['inc'] or 0)
        expenses.append(row['exp'] or 0)

    conn.close()
    return jsonify({
        'labels': labels,
        'incomes': incomes,
        'expenses': expenses
    })

@app.route('/api/charts/category-expenses')
def chart_category_expenses():
    """Expense breakdown for requested or current month."""
    month = request.args.get('month')
    year = request.args.get('year')
    now = datetime.now()
    month = int(month) if month else now.month
    year = int(year) if year else now.year
    m_str = f"{year}-{month:02d}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.name, c.color, SUM(t.amount) as total
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense' AND strftime('%Y-%m', t.transaction_date) = ?
        GROUP BY c.id
        ORDER BY total DESC
    ''', (m_str,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify({
        'labels': [r['name'] for r in rows],
        'colors': [r['color'] for r in rows],
        'data': [r['total'] for r in rows]
    })

@app.route('/api/charts/member-spending')
def chart_member_spending():
    """Spending breakdown by family member for requested or current month."""
    month = request.args.get('month')
    year = request.args.get('year')
    now = datetime.now()
    month = int(month) if month else now.month
    year = int(year) if year else now.year
    m_str = f"{year}-{month:02d}"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.name, m.avatar_color, SUM(t.amount) as total
        FROM transactions t
        JOIN members m ON t.member_id = m.id
        WHERE t.type = 'expense' AND strftime('%Y-%m', t.transaction_date) = ?
        GROUP BY m.id
        ORDER BY total DESC
    ''', (m_str,))
    rows = cursor.fetchall()
    conn.close()

    return jsonify({
        'labels': [r['name'] for r in rows],
        'colors': [r['avatar_color'] for r in rows],
        'data': [r['total'] for r in rows]
    })

# ----------------- EXPORT ROUTES ----------------- #

@app.route('/export/excel')
def export_excel():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    account_id = request.args.get('account_id')
    category_id = request.args.get('category_id')
    member_id = request.args.get('member_id')
    tx_type = request.args.get('type')

    excel_file = export_transactions_to_excel(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        category_id=category_id,
        member_id=member_id,
        tx_type=tx_type
    )

    filename = f"So_Thu_Chi_Gia_Dinh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        excel_file,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

@app.route('/export/csv')
def export_csv():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    account_id = request.args.get('account_id')
    category_id = request.args.get('category_id')
    member_id = request.args.get('member_id')
    tx_type = request.args.get('type')

    csv_file = export_transactions_to_csv(
        start_date=start_date,
        end_date=end_date,
        account_id=account_id,
        category_id=category_id,
        member_id=member_id,
        tx_type=tx_type
    )

    filename = f"So_Thu_Chi_Gia_Dinh_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        csv_file,
        mimetype='text/csv; charset=utf-8',
        as_attachment=True,
        download_name=filename
    )

# ----------------- RESET / SEED DATA ----------------- #

@app.route('/api/reset-data', methods=['POST'])
def reset_data():
    """Allows user to re-seed demo data or wipe database clean."""
    mode = request.form.get('mode', 'sample') # 'sample' or 'clean'
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS transactions")
    cursor.execute("DROP TABLE IF EXISTS budgets")
    cursor.execute("DROP TABLE IF EXISTS goals")
    cursor.execute("DROP TABLE IF EXISTS categories")
    cursor.execute("DROP TABLE IF EXISTS members")
    cursor.execute("DROP TABLE IF EXISTS accounts")
    conn.commit()
    conn.close()

    init_db()
    if mode == 'sample':
        seed_sample_data()

    return jsonify({'success': True, 'message': 'Dữ liệu đã được cập nhật thành công!'})


if __name__ == '__main__':
    init_db()
    seed_sample_data()
    print("=" * 64)
    print(">>> UNG DUNG TAI CHINH GIA DINH DA KHOI DONG THANH CONG! <<<")
    print(">>> TRUY CAP NGAY TAI: http://127.0.0.1:5000 <<<")
    print("=" * 64)
    app.run(host='127.0.0.1', port=5000, debug=False)
