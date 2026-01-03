frappe.pages['mobile-hr'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Mobile HR',
        single_column: true
    });

    // State
    var activeTrip = null;
    var employeeId = null;
    var myExpenses = [];

    // Custom CSS
    var css = '.mobile-hr-container { padding: 15px; background-color: #f4f5f7; min-height: 85vh; }';
    css += '.welcome-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 15px; margin-bottom: 20px; }';
    css += '.welcome-name { font-size: 20px; font-weight: bold; }';
    css += '.welcome-subtitle { font-size: 13px; opacity: 0.9; }';
    css += '.trip-card { background: white; border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }';
    css += '.trip-title { font-size: 16px; font-weight: bold; color: #2c3e50; }';
    css += '.trip-meta { font-size: 12px; color: #7f8c8d; margin-top: 5px; }';
    css += '.btn-checkin { width: 100%; padding: 15px; font-size: 18px; font-weight: bold; background: linear-gradient(145deg, #27ae60, #2ecc71); border: none; color: white; border-radius: 12px; margin-top: 10px; cursor: pointer; }';
    css += '.btn-checkin:disabled { background: #bdc3c7; }';
    css += '.expense-card { background: white; border-radius: 15px; padding: 15px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }';
    css += '.expense-title { font-size: 16px; font-weight: bold; color: #2c3e50; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }';
    css += '.expense-form input { width: 100%; padding: 12px; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px; font-size: 14px; box-sizing: border-box; }';
    css += '.btn-camera { width: 100%; padding: 30px 15px; font-size: 16px; background: #ecf0f1; border: 2px dashed #bdc3c7; border-radius: 12px; color: #7f8c8d; cursor: pointer; margin-bottom: 10px; text-align: center; }';
    css += '.btn-save-expense { width: 100%; padding: 15px; font-size: 16px; font-weight: bold; background: linear-gradient(145deg, #3498db, #2980b9); border: none; color: white; border-radius: 12px; cursor: pointer; }';
    css += '.no-trip-msg { text-align: center; padding: 30px; color: #7f8c8d; }';
    css += '.status-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; background: #d4edda; color: #155724; }';
    css += '.status-draft { background: #fff3cd; color: #856404; }';
    css += '.status-submitted { background: #cce5ff; color: #004085; }';
    css += '#receipt-preview { max-width: 100%; max-height: 150px; border-radius: 8px; margin-bottom: 10px; display: none; }';
    // Expense list styles
    css += '.expense-list { margin-top: 15px; }';
    css += '.expense-item { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: #f8f9fa; border-radius: 10px; margin-bottom: 8px; }';
    css += '.expense-item-info { flex: 1; }';
    css += '.expense-item-desc { font-weight: 500; font-size: 14px; color: #2c3e50; }';
    css += '.expense-item-meta { font-size: 12px; color: #7f8c8d; margin-top: 2px; }';
    css += '.expense-item-amount { font-weight: bold; font-size: 15px; color: #27ae60; margin-right: 10px; }';
    css += '.expense-item-actions { display: flex; gap: 8px; }';
    css += '.expense-item-actions .btn-icon { width: 32px; height: 32px; border-radius: 50%; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }';
    css += '.btn-view { background: #e3f2fd; color: #1976d2; }';
    css += '.btn-delete { background: #ffebee; color: #c62828; }';
    css += '.tab-buttons { display: flex; gap: 10px; margin-bottom: 15px; }';
    css += '.tab-btn { flex: 1; padding: 10px; border: none; border-radius: 8px; font-weight: 500; cursor: pointer; background: #ecf0f1; color: #7f8c8d; }';
    css += '.tab-btn.active { background: #3498db; color: white; }';

    $('<style>').prop('type', 'text/css').html(css).appendTo('head');

    // Main render
    function render() {
        var userName = frappe.session.user_fullname || frappe.session.user;
        var html = '<div class="mobile-hr-container">';
        html += '<div class="welcome-card">';
        html += '<div class="welcome-name">Salom, ' + userName + '</div>';
        html += '<div class="welcome-subtitle">AKFA Mobile HR</div>';
        html += '</div>';
        html += '<div id="trip-section"><div class="text-center"><i class="fa fa-spinner fa-spin"></i> Yuklanmoqda...</div></div>';
        html += '<div id="expense-section" style="margin-top: 20px;"></div>';
        html += '</div>';

        $(wrapper).find('.page-content').html(html);
        loadActiveTrip();
    }

    // Load active trip
    function loadActiveTrip() {
        frappe.call({
            method: 'akfa_accounting.mobile_api.trip_info.get_active_trip',
            callback: function (r) {
                if (r.message && r.message.trip) {
                    activeTrip = r.message.trip;
                    employeeId = r.message.employee;
                    renderTripCard(r.message.trip);
                    loadMyExpenses();
                } else {
                    var msg = r.message && r.message.message ? r.message.message : 'Hozirda aktiv safaringiz yoq';
                    $('#trip-section').html('<div class="trip-card no-trip-msg"><i class="fa fa-info-circle" style="font-size: 40px; margin-bottom: 10px;"></i><br>' + msg + '</div>');
                    renderExpenseSection(false);
                }
            },
            error: function () {
                $('#trip-section').html('<div class="trip-card no-trip-msg">Xatolik yuz berdi</div>');
                renderExpenseSection(false);
            }
        });
    }

    // Load my expenses
    function loadMyExpenses() {
        if (!activeTrip) return;

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Expense Claim',
                filters: {
                    custom_trip_master: activeTrip.name,
                    employee: employeeId
                },
                fields: ['name', 'total_claimed_amount', 'posting_date', 'status', 'docstatus'],
                order_by: 'creation desc',
                limit_page_length: 10
            },
            callback: function (r) {
                myExpenses = r.message || [];
                renderExpenseSection(true);
            },
            error: function () {
                renderExpenseSection(true);
            }
        });
    }

    // Render trip card
    function renderTripCard(trip) {
        var fromDate = trip.from_date || '';
        var toDate = trip.to_date || '';

        var html = '<div class="trip-card">';
        html += '<div style="display: flex; justify-content: space-between; align-items: center;">';
        html += '<div class="trip-title">' + (trip.title || trip.name) + '</div>';
        html += '<span class="status-badge">Aktiv</span>';
        html += '</div>';
        html += '<div class="trip-meta"><i class="fa fa-map-marker"></i> ' + (trip.destination || 'Belgilanmagan') + '</div>';
        html += '<div class="trip-meta"><i class="fa fa-calendar"></i> ' + fromDate + ' - ' + toDate + '</div>';
        html += '<button class="btn-checkin" id="btn-checkin"><i class="fa fa-map-marker"></i> CHECK IN</button>';
        html += '<div id="checkin-status" style="text-align: center; margin-top: 10px; font-size: 13px; color: #7f8c8d;"></div>';
        html += '</div>';

        $('#trip-section').html(html);

        $('#btn-checkin').on('click', function () {
            doCheckIn(trip.name);
        });
    }

    // Do Check-in
    function doCheckIn(tripMaster) {
        if (!navigator.geolocation) {
            frappe.msgprint('GPS qollab-quvvatlanmaydi');
            return;
        }

        var btn = $('#btn-checkin');
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> GPS olinmoqda...');
        $('#checkin-status').text('');

        navigator.geolocation.getCurrentPosition(function (pos) {
            btn.html('<i class="fa fa-spinner fa-spin"></i> Saqlanmoqda...');

            frappe.call({
                method: 'frappe.client.insert',
                args: {
                    doc: {
                        doctype: 'Trip Path Log',
                        trip_master: tripMaster,
                        employee: employeeId,
                        latitude: pos.coords.latitude,
                        longitude: pos.coords.longitude,
                        activity_type: 'Checkpoint',
                        timestamp: frappe.datetime.now_datetime()
                    }
                },
                callback: function (r) {
                    btn.prop('disabled', false).html('<i class="fa fa-map-marker"></i> CHECK IN');
                    if (!r.exc) {
                        $('#checkin-status').html('<i class="fa fa-check" style="color: #27ae60;"></i> Check-in saqlandi!');
                        frappe.show_alert({ message: 'Check-in muvaffaqiyatli', indicator: 'green' });
                    } else {
                        $('#checkin-status').text('Xatolik yuz berdi');
                    }
                },
                error: function () {
                    btn.prop('disabled', false).html('<i class="fa fa-map-marker"></i> CHECK IN');
                    $('#checkin-status').text('Server xatosi');
                }
            });
        }, function (err) {
            btn.prop('disabled', false).html('<i class="fa fa-map-marker"></i> CHECK IN');
            $('#checkin-status').text('GPS xatosi: ' + err.message);
        }, {
            enableHighAccuracy: true,
            timeout: 15000,
            maximumAge: 0
        });
    }

    // Render Expense Section with tabs
    function renderExpenseSection(hasTrip) {
        var html = '<div class="expense-card">';

        if (!hasTrip) {
            html += '<div class="expense-title"><i class="fa fa-money"></i> Harajatlar</div>';
            html += '<div class="no-trip-msg" style="padding: 10px;">Harajat qoshish uchun aktiv safar kerak</div>';
        } else {
            html += '<div class="tab-buttons">';
            html += '<button class="tab-btn active" data-tab="add"><i class="fa fa-plus"></i> Yangi</button>';
            html += '<button class="tab-btn" data-tab="list"><i class="fa fa-list"></i> Royhati (' + myExpenses.length + ')</button>';
            html += '</div>';
            html += '<div id="tab-content"></div>';
        }
        html += '</div>';

        $('#expense-section').html(html);

        if (hasTrip) {
            // Tab click handlers
            $('.tab-btn').on('click', function () {
                $('.tab-btn').removeClass('active');
                $(this).addClass('active');
                var tab = $(this).data('tab');
                if (tab === 'add') {
                    renderExpenseForm();
                } else {
                    renderExpenseList();
                }
            });

            // Show add form by default
            renderExpenseForm();
        }
    }

    // Render expense form
    function renderExpenseForm() {
        var html = '<div class="expense-form">';
        html += '<input type="file" id="receipt-file" accept="image/*" capture="environment" style="display: none;">';
        html += '<img id="receipt-preview" src="" alt="Chek rasmi">';
        html += '<button type="button" class="btn-camera" id="btn-take-photo">';
        html += '<i class="fa fa-camera" style="font-size: 32px; display: block; margin-bottom: 10px;"></i>';
        html += 'Chek rasmini tushiring';
        html += '</button>';
        html += '<input type="number" id="expense-amount" placeholder="Summa kiriting (UZS)" min="0" inputmode="numeric">';
        html += '<input type="text" id="expense-desc" placeholder="Izoh (ixtiyoriy)">';
        html += '<button class="btn-save-expense" id="btn-save-expense"><i class="fa fa-save"></i> Saqlash</button>';
        html += '</div>';

        $('#tab-content').html(html);

        // Camera button click
        $('#btn-take-photo').on('click', function () {
            $('#receipt-file').click();
        });

        // When file selected (photo taken)
        $('#receipt-file').on('change', function (e) {
            var file = e.target.files[0];
            if (file) {
                var reader = new FileReader();
                reader.onload = function (evt) {
                    $('#receipt-preview').attr('src', evt.target.result).show();
                    $('#btn-take-photo').html('<i class="fa fa-check" style="color: #27ae60; font-size: 32px; display: block; margin-bottom: 10px;"></i>Rasm yuklandi').css('border-color', '#27ae60');
                };
                reader.readAsDataURL(file);
            }
        });

        // Save expense
        $('#btn-save-expense').on('click', function () {
            saveExpense();
        });
    }

    // Render expense list
    function renderExpenseList() {
        if (!myExpenses.length) {
            $('#tab-content').html('<div class="no-trip-msg">Hali harajat yoq</div>');
            return;
        }

        var html = '<div class="expense-list">';
        myExpenses.forEach(function (exp) {
            var statusClass = exp.docstatus === 1 ? 'status-submitted' : 'status-draft';
            var statusText = exp.docstatus === 1 ? 'Tasdiqlangan' : 'Qoralama';
            var amount = formatNumber(exp.total_claimed_amount || 0);

            html += '<div class="expense-item" data-name="' + exp.name + '">';
            html += '<div class="expense-item-info">';
            html += '<div class="expense-item-desc">' + exp.name + '</div>';
            html += '<div class="expense-item-meta"><span class="status-badge ' + statusClass + '">' + statusText + '</span> ' + (exp.posting_date || '') + '</div>';
            html += '</div>';
            html += '<div class="expense-item-amount">' + amount + '</div>';
            html += '<div class="expense-item-actions">';
            html += '<button class="btn-icon btn-view" onclick="viewExpense(\'' + exp.name + '\')"><i class="fa fa-eye"></i></button>';
            if (exp.docstatus === 0) {
                html += '<button class="btn-icon btn-delete" onclick="deleteExpense(\'' + exp.name + '\')"><i class="fa fa-trash"></i></button>';
            }
            html += '</div>';
            html += '</div>';
        });
        html += '</div>';

        $('#tab-content').html(html);
    }

    // Format number
    function formatNumber(num) {
        return new Intl.NumberFormat('uz-UZ').format(num) + " so'm";
    }

    // View expense - global function
    window.viewExpense = function (name) {
        frappe.set_route('Form', 'Expense Claim', name);
    };

    // Delete expense - global function
    window.deleteExpense = function (name) {
        frappe.confirm(
            'Bu harajatni ochirishni xohlaysizmi?',
            function () {
                frappe.call({
                    method: 'frappe.client.delete',
                    args: { doctype: 'Expense Claim', name: name },
                    callback: function (r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: 'Ochirildi', indicator: 'green' });
                            loadMyExpenses();
                        }
                    }
                });
            }
        );
    };

    // Save Expense
    function saveExpense() {
        var amount = parseFloat($('#expense-amount').val());
        var desc = $('#expense-desc').val() || 'Mobile harajat';
        var fileInput = $('#receipt-file')[0];

        if (!amount || amount <= 0) {
            frappe.msgprint('Summani kiriting');
            return;
        }

        var btn = $('#btn-save-expense');
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Saqlanmoqda...');

        // Upload file first if exists
        var filePromise = Promise.resolve(null);
        if (fileInput.files.length > 0) {
            filePromise = uploadFile(fileInput.files[0]);
        }

        filePromise.then(function (fileUrl) {
            return frappe.call({
                method: 'akfa_accounting.mobile_api.expense_claim.create_expense_from_mobile',
                args: {
                    trip_master: activeTrip.name,
                    expense_type: 'Others',
                    amount: amount,
                    description: desc,
                    receipt_url: fileUrl
                }
            });
        }).then(function (r) {
            btn.prop('disabled', false).html('<i class="fa fa-save"></i> Saqlash');
            if (r && r.message && r.message.expense_claim_id) {
                frappe.show_alert({ message: 'Harajat saqlandi!', indicator: 'green' });
                // Reset form
                $('#expense-amount').val('');
                $('#expense-desc').val('');
                $('#receipt-preview').hide();
                $('#btn-take-photo').html('<i class="fa fa-camera" style="font-size: 32px; display: block; margin-bottom: 10px;"></i>Chek rasmini tushiring').css('border-color', '#bdc3c7');
                $('#receipt-file').val('');
                // Reload expenses
                loadMyExpenses();
            }
        }).catch(function (err) {
            btn.prop('disabled', false).html('<i class="fa fa-save"></i> Saqlash');
            console.error(err);
            frappe.msgprint('Xatolik: ' + (err.message || 'Server xatosi'));
        });
    }

    // Upload file helper
    function uploadFile(file) {
        return new Promise(function (resolve, reject) {
            var formData = new FormData();
            formData.append('file', file, file.name);
            formData.append('is_private', 0);
            formData.append('folder', 'Home/Attachments');

            $.ajax({
                url: '/api/method/upload_file',
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                headers: {
                    'X-Frappe-CSRF-Token': frappe.csrf_token
                },
                success: function (r) {
                    if (r.message && r.message.file_url) {
                        resolve(r.message.file_url);
                    } else {
                        resolve(null);
                    }
                },
                error: function () {
                    resolve(null);
                }
            });
        });
    }

    // Init
    render();
};
