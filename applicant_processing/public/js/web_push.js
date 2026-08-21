/* =========================================================================
   Applicant Processing - Client Web Push Registration & Subscription Manager
   ========================================================================= */

(function () {
    if (typeof window === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
        return;
    }

    const SW_PATH = "/assets/applicant_processing/js/sw.js";

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/\-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    class WebPushManager {
        constructor() {
            this.registration = null;
            this.vapidPublicKey = null;
            this.initialized = false;
        }

        async init() {
            if (this.initialized) return;
            try {
                this.registration = await navigator.serviceWorker.register(SW_PATH);
                await navigator.serviceWorker.ready;
                this.initialized = true;
                console.log("[WebPush] Service Worker ready. Notification permission:", Notification.permission);

                if (Notification.permission === "granted") {
                    await this.subscribeUser(false);
                } else {
                    this.renderEnablePrompt();
                }
            } catch (err) {
                console.warn("[WebPush] Service Worker registration failed:", err);
                this.renderEnablePrompt();
            }
        }

        async getVapidKey() {
            if (this.vapidPublicKey) return this.vapidPublicKey;
            const r = await frappe.call({
                method: "applicant_processing.applicant_processing.utils.push_api.get_vapid_public_key"
            });
            if (r.message && r.message.public_key) {
                this.vapidPublicKey = r.message.public_key;
                return this.vapidPublicKey;
            }
            throw new Error("Could not retrieve VAPID Public Key from server.");
        }

        async subscribeUser(interactive = true) {
            try {
                if (Notification.permission === "default" && interactive) {
                    const permission = await Notification.requestPermission();
                    if (permission !== "granted") {
                        frappe.show_alert({
                            message: __("Desktop notifications were not enabled."),
                            indicator: "orange"
                        }, 5);
                        return;
                    }
                }

                if (Notification.permission !== "granted") {
                    return;
                }

                const vapidKey = await this.getVapidKey();
                const convertedVapidKey = urlBase64ToUint8Array(vapidKey);

                // Unsubscribe any old mismatched subscription to ensure perfect VAPID alignment
                const existingSub = await this.registration.pushManager.getSubscription();
                if (existingSub) {
                    try {
                        await existingSub.unsubscribe();
                    } catch (e) {}
                }

                const subscription = await this.registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: convertedVapidKey
                });

                const rawKey = subscription.getKey ? subscription.getKey("p256dh") : null;
                const key = rawKey ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawKey))) : "";
                const rawAuthSecret = subscription.getKey ? subscription.getKey("auth") : null;
                const authSecret = rawAuthSecret ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawAuthSecret))) : "";

                // Send subscription to server
                await frappe.call({
                    method: "applicant_processing.applicant_processing.utils.push_api.save_web_push_subscription",
                    args: {
                        endpoint: subscription.endpoint,
                        p256dh: key,
                        auth: authSecret,
                        user_agent: navigator.userAgent
                    }
                });

                if (interactive) {
                    frappe.show_alert({
                        message: __("Chrome Desktop Push Notifications are Active!"),
                        indicator: "green"
                    }, 5);
                    this.removeEnablePrompt();
                }
            } catch (err) {
                console.error("[WebPush] Subscription error:", err);
                if (interactive) {
                    frappe.msgprint({
                        title: __("Notification Setup Failed"),
                        indicator: "red",
                        message: err.message || __("Could not subscribe to Web Push.")
                    });
                }
            }
        }

        renderEnablePrompt() {
            if ($("#webpush-enable-banner").length > 0 || window._webpush_prompt_shown) return;
            window._webpush_prompt_shown = true;

            setTimeout(() => {
                if (Notification.permission !== "granted") {
                    const isDenied = Notification.permission === "denied";

                    if (isDenied) {
                        frappe.msgprint({
                            title: __("🔔 Desktop Notifications are Blocked"),
                            indicator: "orange",
                            message: __(
                                "Chrome has blocked notifications for this site.<br><br>" +
                                "<strong>To receive rectangular alerts on your desktop:</strong><br>" +
                                "1. Look at the Chrome URL address bar above.<br>" +
                                "2. Click the <strong>tune / slider icon 🎚️</strong> on the far left of <code>http://...</code><br>" +
                                "3. Set <strong>Notifications</strong> to <strong>Allow</strong>.<br>" +
                                "4. Refresh this page."
                            )
                        });
                        return;
                    }

                    // Show native Frappe Modal Dialog
                    const d = new frappe.ui.Dialog({
                        title: __("🔔 Enable Chrome Desktop Alerts"),
                        fields: [
                            {
                                fieldname: "html",
                                fieldtype: "HTML",
                                options: `
                                    <div style="text-align: center; padding: 10px 0;">
                                        <div style="font-size: 38px; margin-bottom: 8px;">🔔</div>
                                        <h4 style="margin-bottom: 8px; font-weight: 600;">Stay Updated Everywhere</h4>
                                        <p style="font-size: 13px; color: #64748b; line-height: 1.5; margin: 0 auto; max-width: 360px;">
                                            Receive rectangular popups in the corner of your screen for visas, medical expirations, and candidate alerts — even when you are browsing other websites or this tab is closed.
                                        </p>
                                    </div>
                                `
                            }
                        ],
                        primary_action_label: __("Allow in Chrome"),
                        primary_action: async () => {
                            d.hide();
                            await this.subscribeUser(true);
                        }
                    });

                    d.show();
                }
            }, 600);
        }

        removeEnablePrompt() {
            $("#webpush-enable-banner").fadeOut(200, function() { $(this).remove(); });
            $("#btn-enable-webpush").remove();
        }

        async sendTestPush() {
            return frappe.call({
                method: "applicant_processing.applicant_processing.utils.push_api.send_test_web_push",
                freeze: true,
                freeze_message: __("Dispatching Chrome Desktop Notification..."),
                callback: function (r) {
                    if (!r.exc && r.message && r.message.status === "success") {
                        frappe.msgprint({
                            title: __("Notification Sent"),
                            indicator: "green",
                            message: __("A rectangular notification has been dispatched to Chrome!")
                        });
                    }
                }
            });
        }
    }

    window.ApplicantWebPush = new WebPushManager();

    // Auto-initialize when Frappe Desk is ready
    $(document).on("app_ready", function () {
        window.ApplicantWebPush.init();
    });

    // Also trigger on generic document load
    if (document.readyState === "complete" || document.readyState === "interactive") {
        setTimeout(() => window.ApplicantWebPush.init(), 1500);
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            setTimeout(() => window.ApplicantWebPush.init(), 1500);
        });
    }
})();
