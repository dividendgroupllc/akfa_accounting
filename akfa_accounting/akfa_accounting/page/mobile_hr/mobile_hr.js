frappe.pages['mobile-hr'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Mobile HR',
        single_column: true
    });

    // Custom CSS
    $("<style>")
        .prop("type", "text/css")
        .html(`
            .mobile-hr-container {
                text-align: center;
                padding: 20px;
                background-color: #f4f5f7;
                min-height: 80vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            .btn-checkin {
                width: 200px;
                height: 200px;
                border-radius: 50%;
                font-size: 24px;
                font-weight: bold;
                background: linear-gradient(145deg, #ff5e62, #ff9966);
                border: none;
                color: white;
                box-shadow: 0 10px 30px rgba(255, 94, 98, 0.4);
                margin-top: 30px;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .btn-checkin:hover {
                transform: scale(1.05);
            }
            .btn-checkin:active {
                transform: scale(0.95);
            }
            .status-text {
                margin-top: 20px;
                font-size: 16px;
                color: #555;
                font-weight: 500;
            }
            .welcome-card {
                background: white;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                width: 100%;
                max-width: 320px;
                text-align: left;
            }
            .welcome-title {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
            }
            .welcome-subtitle {
                 font-size: 13px;
                 color: #7f8c8d;
            }
            .action-buttons {
                margin-top: 30px;
                width: 100%;
                max-width: 320px;
            }
            .action-buttons .btn {
                margin-bottom: 10px;
            }
        `)
        .appendTo("head");

    $(wrapper).find('.page-content').html(`
        <div class="mobile-hr-container">
            <div class="welcome-card">
                 <div class="welcome-title">Salom, ${frappe.session.user_fullname || frappe.session.user}</div>
                 <div class="welcome-subtitle">AKFA HR Mobile System</div>
            </div>
            
            <button class="btn-checkin" id="btn-checkin">
                <i class="fa fa-map-marker" style="font-size: 40px;"></i><br>
                CHECK IN
            </button>
            
            <div class="status-text" id="status-text">Joylashuvni saqlash uchun tugmani bosing</div>
            
            <div class="action-buttons">
                <button class="btn btn-default btn-block btn-lg" onclick="frappe.set_route('List', 'Trip Master')">
                    <i class="fa fa-road"></i> Safarlarim
                </button>
                <button class="btn btn-default btn-block btn-lg" onclick="frappe.set_route('List', 'Expense Claim')">
                    <i class="fa fa-money"></i> Harajatlarim
                </button>
            </div>
        </div>
    `);

    $(wrapper).find('#btn-checkin').on('click', function () {
        if (!navigator.geolocation) {
            frappe.msgprint("GPS qo'llab-quvvatlanmaydi");
            return;
        }

        var $btn = $(this);
        $btn.prop('disabled', true);
        $('#status-text').html('<i class="fa fa-spinner fa-spin"></i> GPS olinmoqda...');

        navigator.geolocation.getCurrentPosition(function (position) {
            var lat = position.coords.latitude;
            var lng = position.coords.longitude;

            $('#status-text').text("Saqlanmoqda...");

            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Trip Path Log",
                        latitude: lat,
                        longitude: lng,
                        activity_type: "Checkpoint",
                        timestamp: frappe.datetime.now_datetime()
                    }
                },
                callback: function (r) {
                    $btn.prop('disabled', false);
                    if (!r.exc) {
                        $('#status-text').html('<i class="fa fa-check" style="color:green;"></i> Check-in saqlandi!');
                        frappe.show_alert({ message: "Check-in saqlandi", indicator: 'green' });

                        setTimeout(function () {
                            $('#status-text').text("Joylashuvni saqlash uchun tugmani bosing");
                        }, 3000);
                    } else {
                        $('#status-text').text("Xatolik yuz berdi.");
                    }
                },
                error: function () {
                    $btn.prop('disabled', false);
                    $('#status-text').text("Server xatosi.");
                }
            });
        }, function (err) {
            $btn.prop('disabled', false);
            $('#status-text').text("GPS xatosi: " + err.message);
        }, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        });
    });
};
