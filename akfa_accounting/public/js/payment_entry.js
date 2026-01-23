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
        update_exchange_rate_info(frm);
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
        update_exchange_rate_info(frm);
    },

    refresh: function (frm) {
        if (frm.is_new() && frm.doc.mode_of_payment) {
            load_recent_payments(frm);
        }

        // Set field visibility and requirements
        set_tranzaksiya_turi_visibility(frm);
        update_exchange_rate_info(frm);
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
            load_recent_payments(frm);
            update_exchange_rate_info(frm);
        }
    },

    paid_from: function (frm) {
        // Update balance when paid_from changes
        update_paid_from_balance(frm);
        // Update exchange rate info when account (and thus currency) changes
        setTimeout(function() {
            update_exchange_rate_info(frm);
        }, 500);
    },

    paid_to: function (frm) {
        // Update balance when paid_to changes
        update_paid_to_balance(frm);
        // Update exchange rate info when account (and thus currency) changes
        setTimeout(function() {
            update_exchange_rate_info(frm);
        }, 500);
    },

    paid_from_account_currency: function(frm) {
        update_exchange_rate_info(frm);
    },

    paid_to_account_currency: function(frm) {
        update_exchange_rate_info(frm);
    }
});

function set_tranzaksiya_turi_visibility(frm) {
    // Tranzaksiya turi mandatory faqat Receive da, qolganida hidden
    if (frm.doc.payment_type === 'Receive') {
        frm.set_df_property('custom_tranzaksiya_turi', 'hidden', 0);
        frm.set_df_property('custom_tranzaksiya_turi', 'reqd', 1);
    } else {
        frm.set_df_property('custom_tranzaksiya_turi', 'hidden', 1);
        frm.set_df_property('custom_tranzaksiya_turi', 'reqd', 0);
    }

    // Default: Unlock Party Type for everyone (reset state)
    frm.set_df_property('party_type', 'read_only', 0);

    /**
     * MAIN CASH RESTRICTIONS (maksimum soddalik)
     * For maincash1@gmail.com:
     * - Pay: Party Type is locked
     * - Receive: Party Type is locked to 'Customer'
     */
    if (frappe.session.user === 'maincash1@gmail.com') {
        if (frm.doc.payment_type === 'Pay') {
            frm.set_df_property('party_type', 'read_only', 1);
        } else if (frm.doc.payment_type === 'Receive') {
            // Force Customer and Lock
            if (frm.doc.party_type !== 'Customer') {
                frm.set_value('party_type', 'Customer');
            }
            frm.set_df_property('party_type', 'read_only', 1);
        }
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
            posting_date: frm.doc.posting_date,
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
                    ${format_currency(payment.paid_amount, 'USD')}
                </td>
                <td style="padding: 10px; text-align: right; font-family: monospace;">
                    ${format_currency(payment.received_amount, frm.doc.mode_of_payment)}
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

function format_currency(amount, mode_of_payment) {
    if (!amount) return '0.00';

    // Determine currency based on mode_of_payment
    let symbol = '$ ';

    if (mode_of_payment && mode_of_payment.includes('UZS')) {
        symbol = ' so\'m';
        // Manual formatting for UZS: remove existing symbol if any, append 'so'm'
        return format_number(amount, '#,###.##') + symbol;
    }

    // Default for USD or others
    return symbol + format_number(amount, '#,###.##');
}

function update_exchange_rate_info(frm) {
    // Show exchange rate info when paid_from and paid_to currencies are different
    const from_currency = frm.doc.paid_from_account_currency;
    const to_currency = frm.doc.paid_to_account_currency;
    
    // If currencies are same or not yet set, clear and return
    if (!from_currency || !to_currency || from_currency === to_currency) {
        frm.set_df_property('custom_exchange_rate_info', 'options', '');
        frm.refresh_field('custom_exchange_rate_info');
        return;
    }

    const posting_date = frm.doc.posting_date || frappe.datetime.get_today();

    frappe.call({
        method: 'akfa_accounting.akfa_accounting.api.payment_entry_api.get_daily_exchange_rates',
        args: {
            date: posting_date
        },
        callback: function(r) {
            if (r.message && r.message.usd_to_uzs) {
                const rates = r.message;
                const usd_to_uzs = flt(rates.usd_to_uzs);
                
                // Format rate with thousands separator
                const formatted_rate = format_number(usd_to_uzs, '#,###.##');
                
                // Determine direction based on currencies
                let direction_text = '';
                let main_rate = '';
                
                if (from_currency === 'USD' && to_currency === 'UZS') {
                    direction_text = '1 USD = ' + formatted_rate + ' UZS';
                    main_rate = formatted_rate;
                } else if (from_currency === 'UZS' && to_currency === 'USD') {
                    direction_text = '1 USD = ' + formatted_rate + ' UZS';
                    main_rate = formatted_rate;
                } else {
                    direction_text = '1 USD = ' + formatted_rate + ' UZS';
                    main_rate = formatted_rate;
                }
                
                const html = `
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                padding: 15px 20px; 
                                border-radius: 8px; 
                                color: white;
                                margin: 10px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-size: 12px; opacity: 0.9; margin-bottom: 4px;">
                                    <i class="fa fa-calendar"></i> ${frappe.datetime.str_to_user(rates.date)}
                                </div>
                                <div style="font-size: 11px; opacity: 0.8;">Bugungi kurs</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 24px; font-weight: bold; font-family: monospace;">
                                    ${main_rate}
                                </div>
                                <div style="font-size: 11px; opacity: 0.8;">${direction_text}</div>
                            </div>
                        </div>
                    </div>
                `;
                
                frm.set_df_property('custom_exchange_rate_info', 'options', html);
                frm.refresh_field('custom_exchange_rate_info');
            } else {
                // No rate found
                const html = `
                    <div style="background: #ffebee; 
                                padding: 15px 20px; 
                                border-radius: 8px; 
                                color: #c62828;
                                border: 1px solid #ffcdd2;
                                margin: 10px 0;">
                        <i class="fa fa-exclamation-triangle"></i>
                        <strong>Kurs topilmadi!</strong><br>
                        <span style="font-size: 12px;">
                            ${posting_date} sanasi uchun valyuta kursi mavjud emas. 
                            Currency Exchange ro'yxatiga kurs qo'shing.
                        </span>
                    </div>
                `;
                
                frm.set_df_property('custom_exchange_rate_info', 'options', html);
                frm.refresh_field('custom_exchange_rate_info');
            }
        },
        error: function() {
            frm.set_df_property('custom_exchange_rate_info', 'options', '');
            frm.refresh_field('custom_exchange_rate_info');
        }
    });
}

