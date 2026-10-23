from datetime import datetime, timedelta
import random
from database import get_db_connection, recalculate_all_balances

def seed_sample_data():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) as count FROM categories")
    if cursor.fetchone()['count'] > 0:
        conn.close()
        return

    print("Seeding sample data for Vietnamese family finance...")

    # 1. Accounts
    accounts_data = [
        ('Tiền mặt tại nhà', 'cash', 5000000, 'wallet', '#10b981', '', 'Tiền mặt chi tiêu lặt vặt hàng ngày'),
        ('Vietcombank - Bố', 'bank', 25000000, 'landmark', '#0ea5e9', '0071000888999', 'Tài khoản nhận lương chính'),
        ('Techcombank - Mẹ', 'bank', 18000000, 'landmark', '#ef4444', '1903456789101', 'Tài khoản quản lý chi tiêu gia đình'),
        ('Ví MoMo', 'ewallet', 3000000, 'smartphone', '#d946ef', '0912345678', 'Ví thanh toán online, hóa đơn tiện ích'),
        ('Sổ tiết kiệm BIDV', 'saving', 120000000, 'piggy-bank', '#f59e0b', 'STK-889922', 'Gửi kỳ hạn 6 tháng, lãi suất 5.5%/năm')
    ]
    cursor.executemany('''
        INSERT INTO accounts (name, type, initial_balance, icon, color, account_number, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', accounts_data)

    # 2. Members
    members_data = [
        ('Nguyễn Văn An', 'Bố/Chồng', '#3b82f6', 'Trụ cột tài chính, thu nhập chính'),
        ('Trần Thị Mai', 'Mẹ/Vợ', '#ec4899', 'Tay hòm chìa khóa, phụ trách chi tiêu'),
        ('Nguyễn Minh Khôi', 'Con cái', '#10b981', 'Học sinh cấp 2'),
        ('Quỹ chung gia đình', 'Chung', '#8b5cf6', 'Các khoản chi tiêu chung của gia đình')
    ]
    cursor.executemany('''
        INSERT INTO members (name, role, avatar_color, note)
        VALUES (?, ?, ?, ?)
    ''', members_data)

    # 3. Categories
    # Income categories
    income_categories = [
        ('Tiền lương chính', 'income', 'briefcase', '#10b981', 1),
        ('Tiền thưởng & Hoa hồng', 'income', 'award', '#059669', 1),
        ('Thu nhập làm thêm / Nghề tay trái', 'income', 'trending-up', '#047857', 1),
        ('Tiền lãi tiết kiệm / Cổ tức', 'income', 'percent', '#14b8a6', 1),
        ('Được biếu tặng / Quà biếu', 'income', 'gift', '#06b6d4', 1),
        ('Thu nhập khác', 'income', 'plus-circle', '#64748b', 1)
    ]
    # Expense categories
    expense_categories = [
        ('Ăn uống & Đi chợ siêu thị', 'expense', 'shopping-cart', '#ef4444', 1),
        ('Tiền thuê nhà / Chung cư', 'expense', 'home', '#f97316', 1),
        ('Hóa đơn điện, nước, internet', 'expense', 'zap', '#f59e0b', 1),
        ('Giáo dục & Học phí con', 'expense', 'book-open', '#8b5cf6', 1),
        ('Đi lại, Xăng xe, Grab', 'expense', 'car', '#06b6d4', 1),
        ('Y tế, Thuốc men & Khám bệnh', 'expense', 'heart-pulse', '#ec4899', 1),
        ('Mua sắm vật dụng gia đình', 'expense', 'package', '#6366f1', 1),
        ('Giải trí, Du lịch & Cà phê', 'expense', 'coffee', '#14b8a6', 1),
        ('Hiếu hỉ, Đám cưới, Sinh nhật', 'expense', 'cake', '#a855f7', 1),
        ('Bảo hiểm nhân thọ & Sức khỏe', 'expense', 'shield-check', '#3b82f6', 1),
        ('Chi phí phát sinh khác', 'expense', 'more-horizontal', '#94a3b8', 1)
    ]

    cursor.executemany('''
        INSERT INTO categories (name, type, icon, color, is_default)
        VALUES (?, ?, ?, ?, ?)
    ''', income_categories + expense_categories)

    # 4. Savings Goals
    goals_data = [
        ('Mua ô tô VinFast VF5', 480000000, 180000000, '2027-12-31', 'Mua sắm lớn', '#3b82f6', 'in_progress', 'Kế hoạch nâng cấp xe gia đình'),
        ('Quỹ dự phòng khẩn cấp', 100000000, 75000000, '2026-12-31', 'Khẩn cấp', '#10b981', 'in_progress', 'Đảm bảo chi tiêu tối thiểu 6 tháng'),
        ('Du lịch Đà Nẵng hè', 25000000, 20000000, '2026-07-15', 'Du lịch', '#f59e0b', 'in_progress', 'Chuyến đi nghỉ mát 4 người')
    ]
    cursor.executemany('''
        INSERT INTO goals (name, target_amount, current_amount, deadline, category, color, status, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', goals_data)

    # Fetch mapping IDs
    cursor.execute("SELECT id, name, type FROM categories")
    cats = {row['name']: row['id'] for row in cursor.fetchall()}

    cursor.execute("SELECT id, name FROM accounts")
    accs = {row['name']: row['id'] for row in cursor.fetchall()}

    cursor.execute("SELECT id, name FROM members")
    mems = {row['name']: row['id'] for row in cursor.fetchall()}

    # 5. Budgets for current month & year
    now = datetime.now()
    cur_m = now.month
    cur_y = now.year

    budgets_data = [
        (cats.get('Ăn uống & Đi chợ siêu thị'), cur_m, cur_y, 9000000),
        (cats.get('Hóa đơn điện, nước, internet'), cur_m, cur_y, 2500000),
        (cats.get('Giáo dục & Học phí con'), cur_m, cur_y, 6000000),
        (cats.get('Đi lại, Xăng xe, Grab'), cur_m, cur_y, 2000000),
        (cats.get('Giải trí, Du lịch & Cà phê'), cur_m, cur_y, 3000000),
        (cats.get('Mua sắm vật dụng gia đình'), cur_m, cur_y, 4000000),
        (cats.get('Hiếu hỉ, Đám cưới, Sinh nhật'), cur_m, cur_y, 2000000),
    ]
    for b in budgets_data:
        if b[0]:
            cursor.execute('''
                INSERT INTO budgets (category_id, month, year, amount)
                VALUES (?, ?, ?, ?)
            ''', b)

    # 6. Sample Transactions for the past 90 days
    sample_txs = []

    # Month -2, Month -1, and Current Month
    for days_ago in range(85, -1, -3):
        tx_date = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        d_obj = now - timedelta(days=days_ago)

        # Monthly Salaries around day 5-10
        if d_obj.day in [5, 6]:
            sample_txs.append(('income', 32000000, tx_date, cats.get('Tiền lương chính'), accs.get('Vietcombank - Bố'), None, mems.get('Nguyễn Văn An'), 'Lương công ty tháng ' + str(d_obj.month)))
            sample_txs.append(('income', 18000000, tx_date, cats.get('Tiền lương chính'), accs.get('Techcombank - Mẹ'), None, mems.get('Trần Thị Mai'), 'Lương tháng ' + str(d_obj.month)))

        # Side income / freelance occasionally
        if d_obj.day == 18:
            sample_txs.append(('income', 4500000, tx_date, cats.get('Thu nhập làm thêm / Nghề tay trái'), accs.get('Vietcombank - Bố'), None, mems.get('Nguyễn Văn An'), 'Thù lao tư vấn thiết kế dự án'))

        # Interest
        if d_obj.day == 25:
            sample_txs.append(('income', 550000, tx_date, cats.get('Tiền lãi tiết kiệm / Cổ tức'), accs.get('Sổ tiết kiệm BIDV'), None, mems.get('Quỹ chung gia đình'), 'Lãi tiết kiệm hàng tháng'))

        # Daily Grocery / Food
        sample_txs.append(('expense', random.choice([250000, 380000, 520000, 180000, 650000]), tx_date, cats.get('Ăn uống & Đi chợ siêu thị'), random.choice([accs.get('Techcombank - Mẹ'), accs.get('Tiền mặt tại nhà')]), None, mems.get('Trần Thị Mai'), 'Đi chợ thực phẩm & rau củ gia đình'))

        # Gas / Commute
        if d_obj.day % 7 == 0:
            sample_txs.append(('expense', 300000, tx_date, cats.get('Đi lại, Xăng xe, Grab'), accs.get('Ví MoMo'), None, mems.get('Nguyễn Văn An'), 'Đổ xăng xe máy & ô tô'))

        # Cafe / Friends
        if d_obj.day % 5 == 0:
            sample_txs.append(('expense', random.choice([120000, 180000, 250000]), tx_date, cats.get('Giải trí, Du lịch & Cà phê'), accs.get('Techcombank - Mẹ'), None, random.choice([mems.get('Nguyễn Văn An'), mems.get('Trần Thị Mai')]), 'Cà phê gặp gỡ bạn bè cuối tuần'))

        # Bills around day 12-15
        if d_obj.day == 12:
            sample_txs.append(('expense', 1450000, tx_date, cats.get('Hóa đơn điện, nước, internet'), accs.get('Ví MoMo'), None, mems.get('Trần Thị Mai'), 'Tiền điện sinh hoạt EVN'))
            sample_txs.append(('expense', 320000, tx_date, cats.get('Hóa đơn điện, nước, internet'), accs.get('Ví MoMo'), None, mems.get('Trần Thị Mai'), 'Tiền nước sạch sinh hoạt'))
            sample_txs.append(('expense', 280000, tx_date, cats.get('Hóa đơn điện, nước, internet'), accs.get('Ví MoMo'), None, mems.get('Trần Thị Mai'), 'Cáp quang Internet VNPT'))

        # Tuition around day 10
        if d_obj.day == 10:
            sample_txs.append(('expense', 4500000, tx_date, cats.get('Giáo dục & Học phí con'), accs.get('Techcombank - Mẹ'), None, mems.get('Nguyễn Minh Khôi'), 'Học phí trường & lớp tiếng Anh'))

        # Medical / Pharmacy
        if d_obj.day == 22:
            sample_txs.append(('expense', 450000, tx_date, cats.get('Y tế, Thuốc men & Khám bệnh'), accs.get('Tiền mặt tại nhà'), None, mems.get('Nguyễn Minh Khôi'), 'Mua thuốc & vitamin cho con'))

        # Shopping
        if d_obj.day == 20:
            sample_txs.append(('expense', 1250000, tx_date, cats.get('Mua sắm vật dụng gia đình'), accs.get('Techcombank - Mẹ'), None, mems.get('Trần Thị Mai'), 'Mua nồi chiên không dầu & đồ gia dụng'))

        # Transfers: e.g. Rút tiền mặt hoặc chuyển ví
        if d_obj.day == 1:
            sample_txs.append(('transfer', 3000000, tx_date, None, accs.get('Vietcombank - Bố'), accs.get('Tiền mặt tại nhà'), mems.get('Nguyễn Văn An'), 'Rút tiền ATM chi tiêu gia đình'))
            sample_txs.append(('transfer', 2000000, tx_date, None, accs.get('Vietcombank - Bố'), accs.get('Ví MoMo'), mems.get('Nguyễn Văn An'), 'Nạp tiền vào ví MoMo'))

    for tx in sample_txs:
        cursor.execute('''
            INSERT INTO transactions (type, amount, transaction_date, category_id, account_id, to_account_id, member_id, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', tx)

    conn.commit()
    conn.close()

    # Recalculate account balances accurately
    recalculate_all_balances()
    print("Sample data populated successfully!")

if __name__ == '__main__':
    from database import init_db
    init_db()
    seed_sample_data()
