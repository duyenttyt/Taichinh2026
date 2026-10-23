// Global JS functions for Family Finance App

// Currency Formatter
function formatVND(amount) {
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
}

// Modal open/close helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// Quick Add Transaction Tab switcher
function switchTxTab(type) {
    const typeInput = document.getElementById('txTypeInput');
    if (typeInput) typeInput.value = type;

    const tabIncome = document.getElementById('tab-btn-income');
    const tabExpense = document.getElementById('tab-btn-expense');
    const tabTransfer = document.getElementById('tab-btn-transfer');

    const catGroup = document.getElementById('categorySelectGroup');
    const toAccGroup = document.getElementById('toAccountSelectGroup');
    const fromAccLabel = document.getElementById('fromAccountLabel');

    // Reset styles
    [tabIncome, tabExpense, tabTransfer].forEach(btn => {
        if (!btn) return;
        btn.className = "flex-1 py-2 font-medium text-sm rounded-lg transition-colors text-slate-500 hover:bg-slate-100";
    });

    if (type === 'expense') {
        if (tabExpense) tabExpense.className = "flex-1 py-2 font-semibold text-sm rounded-lg transition-colors bg-red-500 text-white shadow-sm";
        if (catGroup) catGroup.classList.remove('hidden');
        if (toAccGroup) toAccGroup.classList.add('hidden');
        if (fromAccLabel) fromAccLabel.innerText = "Tài khoản / Ví chi tiền";
        filterCategoriesByType('expense');
    } else if (type === 'income') {
        if (tabIncome) tabIncome.className = "flex-1 py-2 font-semibold text-sm rounded-lg transition-colors bg-emerald-500 text-white shadow-sm";
        if (catGroup) catGroup.classList.remove('hidden');
        if (toAccGroup) toAccGroup.classList.add('hidden');
        if (fromAccLabel) fromAccLabel.innerText = "Tài khoản / Ví nhận tiền";
        filterCategoriesByType('income');
    } else if (type === 'transfer') {
        if (tabTransfer) tabTransfer.className = "flex-1 py-2 font-semibold text-sm rounded-lg transition-colors bg-blue-500 text-white shadow-sm";
        if (catGroup) catGroup.classList.add('hidden');
        if (toAccGroup) toAccGroup.classList.remove('hidden');
        if (fromAccLabel) fromAccLabel.innerText = "Chuyển từ Ví / Tài khoản";
    }
}

function filterCategoriesByType(type) {
    const catSelect = document.getElementById('txCategorySelect');
    if (!catSelect) return;
    Array.from(catSelect.options).forEach(opt => {
        if (opt.value === "") return;
        const optType = opt.getAttribute('data-type');
        if (optType === type) {
            opt.style.display = "";
        } else {
            opt.style.display = "none";
        }
    });
    // Pick first matching
    const firstMatch = Array.from(catSelect.options).find(opt => opt.value !== "" && opt.getAttribute('data-type') === type);
    if (firstMatch) catSelect.value = firstMatch.value;
}

// Quick Add Form Submit
document.addEventListener('DOMContentLoaded', () => {
    const quickAddForm = document.getElementById('quickAddForm');
    if (quickAddForm) {
        quickAddForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(quickAddForm);

            try {
                const res = await fetch('/api/transactions', {
                    method: 'POST',
                    body: formData
                });
                const result = await res.json();
                if (result.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Thành công!',
                        text: result.message,
                        timer: 1500,
                        showConfirmButton: false
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Lỗi', result.message, 'error');
                }
            } catch (err) {
                Swal.fire('Lỗi', 'Không thể kết nối máy chủ', 'error');
            }
        });
    }

    // Default tab expense
    switchTxTab('expense');
});

// Delete Transaction
async function deleteTransaction(txId) {
    const confirm = await Swal.fire({
        title: 'Xóa giao dịch này?',
        text: 'Hành động này không thể hoàn tác và số dư tài khoản sẽ được tính toán lại!',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Đồng ý xóa',
        cancelButtonText: 'Hủy bỏ'
    });

    if (confirm.isConfirmed) {
        try {
            const res = await fetch(`/api/transactions/${txId}/delete`, { method: 'POST' });
            const result = await res.json();
            if (result.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Đã xóa!',
                    text: result.message,
                    timer: 1200,
                    showConfirmButton: false
                }).then(() => window.location.reload());
            } else {
                Swal.fire('Lỗi', result.message, 'error');
            }
        } catch (err) {
            Swal.fire('Lỗi', 'Có lỗi xảy ra', 'error');
        }
    }
}

// Reset / Seed Data
async function resetDemoData(mode) {
    const msg = mode === 'clean' 
        ? 'Bạn có chắc muốn XÓA TRẮNG toàn bộ dữ liệu để bắt đầu nhập dữ liệu gia đình bạn?' 
        : 'Bạn có chắc muốn KHÔI PHỤC lại dữ liệu mẫu đầy đủ ban đầu?';

    const confirm = await Swal.fire({
        title: 'Xác nhận thao tác dữ liệu',
        text: msg,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3b82f6',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Xác nhận thực hiện',
        cancelButtonText: 'Hủy bỏ'
    });

    if (confirm.isConfirmed) {
        const formData = new FormData();
        formData.append('mode', mode);
        try {
            const res = await fetch('/api/reset-data', { method: 'POST', body: formData });
            const result = await res.json();
            if (result.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Đã hoàn tất',
                    text: result.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    window.location.href = '/';
                });
            }
        } catch (err) {
            Swal.fire('Lỗi', 'Có lỗi xảy ra', 'error');
        }
    }
}
