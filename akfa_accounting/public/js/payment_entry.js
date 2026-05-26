frappe.ui.form.on('Payment Entry', {
    onload: function (frm) {
        // TASK 1: Hide "Pay" payment type for "davron kassa" role (per-form instance)
        filter_payment_type_options(frm);
        // Create a container for recent payments at the end of form
        if (!frm.$recent_payments_container) {
            frm.$recent_payments_container = $('<div class="form-section" style="margin-top: 30px;"></div>');
            frm.$wrapper.find('.form-layout').append(frm.$recent_payments_container);
        }

        // Hide plumbing fields for "Maximum Simplicity"
        frm.set_df_property('naming_series', 'hidden', 1);
        frm.set_df_property('company', 'hidden', 1);
        frm.set_df_property('cost_center', 'hidden', 1);
        frm.set_df_property('dimension_col_break', 'hidden', 1);

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
        // TASK 1: Filter payment type options on every refresh
        filter_payment_type_options(frm);

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

    party: function(frm) {
        // After party set, re-pick paid_from/paid_to to match mode_of_payment currency.
        sync_party_account_to_mode_currency(frm);
    },

    paid_from_account_currency: function(frm) {
        update_exchange_rate_info(frm);
        update_currency_labels(frm);
    },

    paid_to_account_currency: function(frm) {
        update_exchange_rate_info(frm);
        update_currency_labels(frm);
    },

    received_amount: function(frm) {
        // Backward calc: ERPNext only auto-derives received_amount from paid_amount.
        // When cashier knows the cash side (received) and needs invoice side (paid),
        // compute paid_amount from received_amount using the same exchange-rate logic.
        backward_calc_paid_amount(frm);
    }
});

function backward_calc_paid_amount(frm) {
    if (frm._akfa_backward_calc_in_progress) return;

    const src_cur = frm.doc.paid_from_account_currency;
    const dst_cur = frm.doc.paid_to_account_currency;
    if (!src_cur || !dst_cur || src_cur === dst_cur) return;

    const received = flt(frm.doc.received_amount);
    if (!received) return;

    let source_rate = flt(frm.doc.source_exchange_rate);
    let target_rate = flt(frm.doc.target_exchange_rate);

    // ERPNext fallback: missing source rate when reverse Currency Exchange row is absent.
    // Use the displayed USD<->UZS rate as fallback so cashier-entered values still resolve.
    const need_fallback = !source_rate || (source_rate === 1 && src_cur !== frappe.boot.sysdefaults.currency);
    if (need_fallback || !target_rate) {
        frappe.call({
            method: 'akfa_accounting.akfa_accounting.api.payment_entry_api.get_daily_exchange_rates',
            args: { date: frm.doc.posting_date || frappe.datetime.get_today() },
            callback: function(r) {
                if (!r.message || !r.message.usd_to_uzs) return;
                const usd_to_uzs = flt(r.message.usd_to_uzs);
                apply_backward_calc(frm, received, src_cur, dst_cur, usd_to_uzs);
            }
        });
        return;
    }

    const company_amount = received * target_rate;
    const new_paid = company_amount / source_rate;
    commit_paid_amount(frm, new_paid);
}

function apply_backward_calc(frm, received, src_cur, dst_cur, usd_to_uzs) {
    let new_paid = null;

    if (src_cur === 'USD' && dst_cur === 'UZS') {
        // paid USD -> received UZS. Reverse: paid_USD = received_UZS / rate
        new_paid = received / usd_to_uzs;
    } else if (src_cur === 'UZS' && dst_cur === 'USD') {
        // paid UZS -> received USD. Reverse: paid_UZS = received_USD * rate
        new_paid = received * usd_to_uzs;
    }

    if (new_paid !== null) {
        commit_paid_amount(frm, new_paid);
    }
}

function commit_paid_amount(frm, new_paid) {
    if (Math.abs(flt(frm.doc.paid_amount) - new_paid) < 0.01) return;
    frm._akfa_backward_calc_in_progress = true;
    frm.set_value('paid_amount', new_paid).then(() => {
        // Restore received_amount because ERPNext's forward calc may have overwritten it
        // when we set paid_amount (round-trip drift on rounding).
        frm._akfa_backward_calc_in_progress = false;
    });
}

// TASK 1: Filter payment type options based on user role
function filter_payment_type_options(frm) {
    // Check if user has "davron kassa" role AND is NOT Administrator
    if (frappe.user.has_role('davron kassa') && !frappe.user.has_role('Administrator')) {
        // Wait for field to be fully rendered
        setTimeout(function() {
            const field = frm.get_field('payment_type');
            if (field && field.$input) {
                // Direct DOM manipulation: Remove "Pay" option from select dropdown
                field.$input.find('option[value="Pay"]').remove();

                // If current value is "Pay", change it to "Receive"
                if (frm.doc.payment_type === 'Pay') {
                    frm.set_value('payment_type', 'Receive');
                }

                console.log('[TASK 1] "Pay" option hidden for davron kassa role');
            }
        }, 100);
    }
}

function set_tranzaksiya_turi_visibility(frm) {
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
                // TASK 2: Don't auto-populate paid_to for Internal Transfer
                if (defaults.paid_to && frm.doc.payment_type !== 'Internal Transfer') {
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
    // Label currency must follow account currency, NOT mode_of_payment.
    // paid_amount = paid_from currency; received_amount = paid_to currency.
    let fallback = 'USD';
    if (frm.doc.mode_of_payment && frm.doc.mode_of_payment.includes('UZS')) {
        fallback = 'UZS';
    }

    const paid_currency = frm.doc.paid_from_account_currency || fallback;
    const received_currency = frm.doc.paid_to_account_currency || fallback;

    frm.set_df_property('paid_amount', 'label', `Paid Amount (${paid_currency})`);
    frm.set_df_property('received_amount', 'label', `Received Amount (${received_currency})`);

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
                    ${format_amount_by_currency(payment.paid_amount, payment.paid_from_account_currency)}
                </td>
                <td style="padding: 10px; text-align: right; font-family: monospace;">
                    ${format_amount_by_currency(payment.received_amount, payment.paid_to_account_currency)}
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

    let symbol = '$ ';

    if (mode_of_payment && mode_of_payment.includes('UZS')) {
        symbol = ' so\'m';
        return format_number(amount, '#,###.##') + symbol;
    }

    return symbol + format_number(amount, '#,###.##');
}

// Format amount by explicit currency code (USD, UZS, etc.) from PE row.
function format_amount_by_currency(amount, currency) {
    if (!amount) return '0.00';
    if (currency === 'UZS') {
        return format_number(amount, '#,###.##') + ' so\'m';
    }
    if (currency === 'USD') {
        return '$ ' + format_number(amount, '#,###.##');
    }
    return format_number(amount, '#,###.##') + ' ' + (currency || '');
}

function sync_party_account_to_mode_currency(frm) {
    // Ensure paid_from (Receive) / paid_to (Pay) currency matches mode_of_payment currency.
    if (!frm.doc.party_type || !frm.doc.party || !frm.doc.company || !frm.doc.mode_of_payment) {
        return;
    }

    const mode_currency = frm.doc.mode_of_payment.includes('UZS') ? 'UZS' : 'USD';

    frappe.call({
        method: 'akfa_accounting.akfa_accounting.api.payment_entry_api.get_party_account_for_currency',
        args: {
            party_type: frm.doc.party_type,
            party: frm.doc.party,
            company: frm.doc.company,
            currency: mode_currency
        },
        callback: function(r) {
            if (!r.message) {
                frappe.show_alert({
                    message: __(`${frm.doc.party} uchun ${mode_currency} valyutadagi hisob topilmadi. Multi-currency PE bo'lishi mumkin.`),
                    indicator: 'orange'
                }, 7);
                return;
            }

            const account = r.message.account;
            if (frm.doc.payment_type === 'Receive') {
                if (frm.doc.paid_from !== account) {
                    frm.set_value('paid_from', account);
                }
            } else if (frm.doc.payment_type === 'Pay') {
                if (frm.doc.paid_to !== account) {
                    frm.set_value('paid_to', account);
                }
            }

            if (!r.message.matched) {
                frappe.show_alert({
                    message: __(`Diqqat: ${frm.doc.party} default hisobi boshqa valyutada. Fallback ${mode_currency} hisob tanlandi.`),
                    indicator: 'orange'
                }, 7);
            }
        }
    });
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
                const is_stale = rates.date !== rates.requested_date;

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

                const bg_gradient = is_stale
                    ? 'linear-gradient(135deg, #f39c12 0%, #d35400 100%)'
                    : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                const label_text = is_stale
                    ? `Eskirgan kurs (${rates.date})`
                    : 'Bugungi kurs';

                const html = `
                    <div style="background: ${bg_gradient};
                                padding: 15px 20px;
                                border-radius: 8px;
                                color: white;
                                margin: 10px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-size: 12px; opacity: 0.9; margin-bottom: 4px;">
                                    <i class="fa fa-calendar"></i> ${frappe.datetime.str_to_user(rates.date)}
                                </div>
                                <div style="font-size: 11px; opacity: 0.8;">${label_text}</div>
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
