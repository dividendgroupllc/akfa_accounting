frappe.ui.form.on('Payment Entry', {
    onload: function(frm) {
        // Create a container for recent payments at the end of form
        if (!frm.$recent_payments_container) {
            frm.$recent_payments_container = $('<div class="form-section" style="margin-top: 30px;"></div>');
            frm.$wrapper.find('.form-layout').append(frm.$recent_payments_container);
        }
    },

    mode_of_payment: function(frm) {
        if (frm.doc.mode_of_payment && frm.is_new()) {
            load_recent_payments(frm);
        } else if (!frm.doc.mode_of_payment && frm.is_new()) {
            clear_recent_payments(frm);
        }
    },

    refresh: function(frm) {
        if (frm.is_new() && frm.doc.mode_of_payment) {
            load_recent_payments(frm);
        }
    }
});

function clear_recent_payments(frm) {
    if (frm.$recent_payments_container) {
        frm.$recent_payments_container.empty();
    }
}

function load_recent_payments(frm, page = 1) {
    const mode_of_payment = frm.doc.mode_of_payment;

    if (!mode_of_payment) {
        clear_recent_payments(frm);
        return;
    }

    const limit = 50;
    const start = (page - 1) * limit;

    frappe.call({
        method: 'akfa_accounting.akfa_accounting.api.payment_entry_api.get_recent_payments',
        args: {
            mode_of_payment: mode_of_payment,
            start: start,
            limit: limit
        },
        callback: function(r) {
            if (r.message && r.message.data) {
                render_recent_payments(frm, r.message, page);
            } else {
                render_no_data(frm, mode_of_payment);
            }
        }
    });
}

function render_no_data(frm, mode_of_payment) {
    if (!frm.$recent_payments_container) return;

    const html = `
        <div class="frappe-card" style="padding: 20px; background: #f8f9fa; border: 1px solid #d1d8dd; border-radius: 4px;">
            <h4 style="margin-bottom: 10px;">${__('Recent Transactions')}</h4>
            <p class="text-muted">${__('No recent transactions found for')} <strong>${mode_of_payment}</strong></p>
        </div>
    `;

    frm.$recent_payments_container.html(html);
}

function render_recent_payments(frm, response, page) {
    if (!frm.$recent_payments_container) return;

    const data = response.data;
    const total = response.total;
    const total_pages = response.total_pages;

    if (!data || data.length === 0) {
        render_no_data(frm, frm.doc.mode_of_payment);
        return;
    }

    let html = `
        <div class="frappe-card" style="padding: 20px; background: #f8f9fa; border: 1px solid #d1d8dd; border-radius: 4px;">
            <div style="margin-bottom: 15px;">
                <h4 style="margin-bottom: 5px;">${__('Recent Transactions for')} <strong>${frm.doc.mode_of_payment}</strong></h4>
                <p class="text-muted" style="margin-bottom: 0; font-size: 13px;">
                    ${__('Total')}: <strong>${total}</strong> ${__('transactions')}
                </p>
            </div>

            <div class="table-responsive" style="max-height: 500px; overflow-y: auto; background: white; border: 1px solid #d1d8dd; border-radius: 4px;">
                <table class="table table-bordered table-hover" style="margin-bottom: 0;">
                    <thead style="position: sticky; top: 0; background: #f0f4f7; z-index: 10;">
                        <tr>
                            <th style="padding: 12px; border-bottom: 2px solid #d1d8dd;">${__('ID')}</th>
                            <th style="padding: 12px; border-bottom: 2px solid #d1d8dd;">${__('Date')}</th>
                            <th style="padding: 12px; border-bottom: 2px solid #d1d8dd;">${__('Party Type')}</th>
                            <th style="padding: 12px; border-bottom: 2px solid #d1d8dd;">${__('Party')}</th>
                            <th style="padding: 12px; text-align: right; border-bottom: 2px solid #d1d8dd;">${__('Paid Amount')}</th>
                            <th style="padding: 12px; text-align: right; border-bottom: 2px solid #d1d8dd;">${__('Received Amount')}</th>
                            <th style="padding: 12px; border-bottom: 2px solid #d1d8dd;">${__('Status')}</th>
                        </tr>
                    </thead>
                    <tbody>
    `;

    data.forEach((payment, index) => {
        const status_color = get_status_color(payment.status);
        const row_bg = index % 2 === 0 ? '#ffffff' : '#f8f9fa';

        html += `
            <tr style="cursor: pointer; background: ${row_bg};" class="payment-row" data-name="${payment.name}">
                <td style="padding: 10px;">
                    <a href="#Form/Payment Entry/${payment.name}" class="text-primary">${payment.name}</a>
                </td>
                <td style="padding: 10px;">${frappe.datetime.str_to_user(payment.posting_date)}</td>
                <td style="padding: 10px;">${payment.party_type || '-'}</td>
                <td style="padding: 10px;">${payment.party || '-'}</td>
                <td style="padding: 10px; text-align: right; font-family: monospace;">
                    ${format_currency(payment.paid_amount)}
                </td>
                <td style="padding: 10px; text-align: right; font-family: monospace;">
                    ${format_currency(payment.received_amount)}
                </td>
                <td style="padding: 10px;">
                    <span class="indicator-pill ${status_color}" style="font-size: 11px;">
                        ${payment.status}
                    </span>
                </td>
            </tr>
        `;
    });

    html += `
                    </tbody>
                </table>
            </div>
    `;

    // Pagination
    if (total_pages > 1) {
        html += `
            <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #d1d8dd; text-align: center;">
                <button class="btn btn-default btn-sm prev-page-btn" data-page="${page}" ${page === 1 ? 'disabled' : ''}>
                    <i class="fa fa-chevron-left"></i> ${__('Previous')}
                </button>
                <span style="margin: 0 20px; font-size: 14px; color: #6c757d;">
                    ${__('Page')} <strong>${page}</strong> ${__('of')} <strong>${total_pages}</strong>
                </span>
                <button class="btn btn-default btn-sm next-page-btn" data-page="${page}" ${page === total_pages ? 'disabled' : ''}>
                    ${__('Next')} <i class="fa fa-chevron-right"></i>
                </button>
            </div>
        `;
    }

    html += `</div>`;

    frm.$recent_payments_container.html(html);

    // Event handlers
    frm.$recent_payments_container.find('.prev-page-btn').on('click', function() {
        const currentPage = parseInt($(this).data('page'));
        if (currentPage > 1) {
            load_recent_payments(frm, currentPage - 1);
        }
    });

    frm.$recent_payments_container.find('.next-page-btn').on('click', function() {
        const currentPage = parseInt($(this).data('page'));
        if (currentPage < total_pages) {
            load_recent_payments(frm, currentPage + 1);
        }
    });

    frm.$recent_payments_container.find('.payment-row').on('click', function(e) {
        if (!$(e.target).is('a')) {
            const paymentName = $(this).data('name');
            frappe.set_route('Form', 'Payment Entry', paymentName);
        }
    });
}

function get_status_color(status) {
    const status_colors = {
        'Draft': 'gray',
        'Submitted': 'blue',
        'Cancelled': 'red',
        'Paid': 'green',
        'Return': 'orange',
        'Partly Paid': 'yellow'
    };
    return status_colors[status] || 'gray';
}

function format_currency(amount) {
    if (!amount) return '0.00';
    return frappe.format(amount, {fieldtype: 'Currency'});
}
