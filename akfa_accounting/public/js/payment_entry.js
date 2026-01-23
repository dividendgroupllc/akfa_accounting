frappe.ui.form.on('Payment Entry', {
    onload: function (frm) {
        // Create a container for recent payments at the end of form
        if (!frm.$recent_payments_container) {
            frm.$recent_payments_container = $('<div class="form-section" style="margin-top: 30px;"></div>');
            frm.$wrapper.find('.form-layout').append(frm.$recent_payments_container);
        }

        // Hide plumbing fields for "Maximum Simplicity"
        frm.set_df_property('naming_series', 'hidden', 1);
        frm.set_df_property('company', 'hidden', 1);

        // Set initial field visibility and requirements based on payment_type
        set_tranzaksiya_turi_visibility(frm);
    },

    mode_of_payment: function (frm) {
        if (frm.doc.mode_of_payment && frm.is_new()) {
            load_recent_payments(frm);
        } else if (!frm.doc.mode_of_payment && frm.is_new()) {
            clear_recent_payments(frm);
        }

        // Auto-fill fields based on payment_type and mode_of_payment
        apply_payment_entry_defaults(frm);

        // Update field labels with correct currency
        update_currency_labels(frm);
    },

    refresh: function (frm) {
        if (frm.is_new() && frm.doc.mode_of_payment) {
            load_recent_payments(frm);
        }

        // Set field visibility and requirements
        set_tranzaksiya_turi_visibility(frm);
    },

    payment_type: function (frm) {
        // Handle field visibility when payment_type changes
        set_tranzaksiya_turi_visibility(frm);
        apply_payment_entry_defaults(frm);
    },

    posting_date: function (frm) {
        // Update balances when date changes
        if (frm.doc.mode_of_payment) {
            apply_payment_entry_defaults(frm);
        }
    },

    paid_from: function (frm) {
        // Update balance when paid_from changes
        update_paid_from_balance(frm);
    },

    paid_to: function (frm) {
        // Update balance when paid_to changes
        update_paid_to_balance(frm);
    }
});

function set_tranzaksiya_turi_visibility(frm) {
    // Tranzaksiya turi mandatory faqat Receive da, qolganida hidden
    if (frm.doc.payment_type === 'Receive') {
        frm.set_df_property('custom_tranzaksiya_turi', 'hidden', 0);
        frm.set_df_property('custom_tranzaksiya_turi', 'reqd', 1);

        // Unlock party_type for Receive triggers
        frm.set_df_property('party_type', 'read_only', 0);
    } else {
        frm.set_df_property('custom_tranzaksiya_turi', 'hidden', 1);
        frm.set_df_property('custom_tranzaksiya_turi', 'reqd', 0);
    }

    // MAXIMALLY SIMPLE: Lock Party Type if it is 'Pay' ONLY for maincash1@gmail.com
    if (frm.doc.payment_type === 'Pay' && frappe.session.user === 'maincash1@gmail.com') {
        frm.set_df_property('party_type', 'read_only', 1);
    } else {
        // Unlock it for others or if not Pay (so admins/others aren't blocked)
        frm.set_df_property('party_type', 'read_only', 0);
    }
}

function apply_payment_entry_defaults(frm) {
    // Call server-side method to get default values
    if (!frm.doc.payment_type || !frm.doc.mode_of_payment || !frm.doc.company || !frm.doc.posting_date) {
        return;
    }

    frappe.call({
        method: 'akfa_accounting.akfa_accounting.api.payment_entry_api.get_payment_entry_defaults',
        args: {
            payment_type: frm.doc.payment_type,
            mode_of_payment: frm.doc.mode_of_payment,
            company: frm.doc.company,
            posting_date: frm.doc.posting_date
        },
        callback: function (r) {
            if (r.message && Object.keys(r.message).length > 0) {
                const defaults = r.message;

                // Set accounts and party first
                if (defaults.paid_from) {
                    frm.set_value('paid_from', defaults.paid_from);
                }
                if (defaults.paid_to) {
                    frm.set_value('paid_to', defaults.paid_to);
                }
                if (defaults.party_type) {
                    frm.set_value('party_type', defaults.party_type);
                }
                if (defaults.party) {
                    frm.set_value('party', defaults.party);
                }

                // Set balances after a delay to override ERPNext's default behavior
                setTimeout(function () {
                    if (defaults.paid_from_account_balance !== undefined) {
                        frm.set_value('paid_from_account_balance', defaults.paid_from_account_balance);
                    }
                    if (defaults.paid_to_account_balance !== undefined) {
                        frm.set_value('paid_to_account_balance', defaults.paid_to_account_balance);
                    }
                }, 500);

                // HARDCODED RULE: Davron can only pay to the default 'Ofis' party.
                if (frappe.session.user === 'maincash1@gmail.com') {
                    frm.set_df_property('party', 'read_only', 1);
                }
            }
        }
    });
}

function update_paid_from_balance(frm) {
    if (frm.doc.paid_from && frm.doc.posting_date) {
        // Use setTimeout to ensure this runs after ERPNext's handlers
        setTimeout(function () {
            frappe.call({
                method: 'erpnext.accounts.utils.get_balance_on',
                args: {
                    account: frm.doc.paid_from,
                    date: frm.doc.posting_date
                },
                callback: function (r) {
                    if (r.message !== undefined) {
                        frm.set_value('paid_from_account_balance', r.message);
                    }
                }
            });
        }, 300);
    }
}

function update_paid_to_balance(frm) {
    if (frm.doc.paid_to && frm.doc.posting_date) {
        // Use setTimeout to ensure this runs after ERPNext's handlers
        setTimeout(function () {
            frappe.call({
                method: 'erpnext.accounts.utils.get_balance_on',
                args: {
                    account: frm.doc.paid_to,
                    date: frm.doc.posting_date
                },
                callback: function (r) {
                    if (r.message !== undefined) {
                        frm.set_value('paid_to_account_balance', r.message);
                    }
                }
            });
        }, 300);
    }
}

function update_currency_labels(frm) {
    // Update field labels based on currency from mode of payment
    if (!frm.doc.mode_of_payment) {
        return;
    }

    let currency = 'USD';
    let currency_symbol = '$';

    if (frm.doc.mode_of_payment.includes('UZS')) {
        currency = 'UZS';
        currency_symbol = 'so\'m';
    }

    // Update field labels
    frm.set_df_property('paid_amount', 'label', `Paid Amount (${currency})`);
    frm.set_df_property('received_amount', 'label', `Received Amount (${currency})`);

    // Refresh fields to show new labels
    frm.refresh_field('paid_amount');
    frm.refresh_field('received_amount');
}

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
        callback: function (r) {
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
    frm.$recent_payments_container.find('.prev-page-btn').on('click', function () {
        const currentPage = parseInt($(this).data('page'));
        if (currentPage > 1) {
            load_recent_payments(frm, currentPage - 1);
        }
    });

    frm.$recent_payments_container.find('.next-page-btn').on('click', function () {
        const currentPage = parseInt($(this).data('page'));
        if (currentPage < total_pages) {
            load_recent_payments(frm, currentPage + 1);
        }
    });

    frm.$recent_payments_container.find('.payment-row').on('click', function (e) {
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
    return frappe.format(amount, { fieldtype: 'Currency' });
}
