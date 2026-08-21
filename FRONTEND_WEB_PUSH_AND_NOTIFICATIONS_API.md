# Frontend Integration Guide: Web Push & System Notification APIs

This document outlines the **Web Push Notification subsystem**, **Service Worker architecture**, and **all recent backend APIs** for the frontend team. It provides copy-paste ready JavaScript code, payload specifications, API request/response formats, and testing procedures.

---

## 1. Architecture Overview

```
 ┌────────────────────────────────────────────────────────┐
 │                   BROWSER CLIENT                       │
 │  (React / Vue / Frappe Desk / Agency Portal Frontend)  │
 └─────────────────────────┬──────────────────────────────┘
                           │ 1. GET /api/method/...get_vapid_public_key
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │                FRAPPE BACKEND SERVER                   │
 │           (Notification Config / VAPID ECDSA)          │
 └─────────────────────────┬──────────────────────────────┘
                           │ 2. Return ApplicationServerKey (P-256 Base64)
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │              GOOGLE FCM / PUSH SERVICE                 │
 │           (registration.pushManager.subscribe)         │
 └─────────────────────────┬──────────────────────────────┘
                           │ 3. Return PushSubscription (endpoint, p256dh, auth)
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │           SAVE SUBSCRIPTION TO FRAPPE DB               │
 │       (DocType: Web Push Subscription per User)        │
 └─────────────────────────┬──────────────────────────────┘
                           │
                           │ 4. Event Occurs (Visa Stamped, Medical Countdown, Wakala Alert)
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │                 BACKGROUND DISPATCH                    │
 │             (PyWebPush + Service Worker)               │
 └─────────────────────────┬──────────────────────────────┘
                           │
                           ▼
 ┌────────────────────────────────────────────────────────┐
 │          OS NATIVE RECTANGULAR POPUP ON DESKTOP        │
 │     (Appears even if user is on other sites / closed)   │
 └────────────────────────────────────────────────────────┘
```

---

## 2. Frontend Web Push APIs

### 2.1 Get VAPID Public Key
Retrieves the application server key needed to subscribe the browser via `pushManager.subscribe`.

* **Endpoint:** `GET` / `POST` `/api/method/applicant_processing.applicant_processing.utils.push_api.get_vapid_public_key`
* **Access:** Public (`allow_guest=True`)
* **Request Headers:**
  ```http
  Accept: application/json
  ```
* **Response (HTTP 200):**
  ```json
  {
    "message": {
      "public_key": "BBoijYa6nfblI5iPhXyBmdA8nKYJUzgs1H3-zZGsyVIBYOWaUps-j2SE8rh4Jfm81hFjLd33EEcQzXxYsrlSqU8",
      "enabled": 1
    }
  }
  ```

---

### 2.2 Register / Save Web Push Subscription
Saves the user's browser push subscription credentials in the Frappe backend.

* **Endpoint:** `POST` `/api/method/applicant_processing.applicant_processing.utils.push_api.save_web_push_subscription`
* **Access:** Authenticated User (Session Cookie or `Authorization: token key:secret`)
* **Request Headers:**
  ```http
  Content-Type: application/json
  ```
* **Request Body:**
  ```json
  {
    "endpoint": "https://fcm.googleapis.com/fcm/send/fcX33UeQDQ4:APA91bFrK5...",
    "p256dh": "BCVxsr7N_eXbM4lF8qQ59Vn6A7Gk8sP0d2lKm1nOp...",
    "auth": "5Jk9a0mP3qZ4x8y1...",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0"
  }
  ```
* **Response (HTTP 200):**
  ```json
  {
    "message": {
      "status": "success",
      "message": "Subscribed to Web Push notifications."
    }
  }
  ```

---

### 2.3 Send Test Push Notification
Dispatches an instant test rectangular notification to all active devices registered to the logged-in user.

* **Endpoint:** `POST` `/api/method/applicant_processing.applicant_processing.utils.push_api.send_test_web_push`
* **Access:** Authenticated User
* **Response (HTTP 200):**
  ```json
  {
    "message": {
      "status": "success",
      "message": "Test push notification dispatched to 1 active device(s)!"
    }
  }
  ```

---

## 3. Frontend Client-Side Implementation (Ready to Copy-Paste)

### 3.1 `web_push_client.js` (Frontend Subscription Manager)

```javascript
/**
 * Helper: Converts Base64 URL-safe VAPID key to Uint8Array for PushManager
 */
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

/**
 * Initializes Service Worker & Subscribes User to Push Notifications
 */
export async function initializeWebPush() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
        console.warn("[WebPush] Push notifications are not supported in this browser.");
        return { supported: false };
    }

    try {
        // 1. Register Service Worker
        const registration = await navigator.serviceWorker.register("/assets/applicant_processing/js/sw.js");
        await navigator.serviceWorker.ready;

        // 2. Request Notification Permission
        if (Notification.permission === "default") {
            const permission = await Notification.requestPermission();
            if (permission !== "granted") {
                return { status: "denied", message: "User dismissed or blocked notifications." };
            }
        }

        if (Notification.permission === "denied") {
            return { status: "denied", message: "Notifications blocked in browser settings." };
        }

        // 3. Fetch VAPID Public Key from Frappe backend
        const res = await fetch("/api/method/applicant_processing.applicant_processing.utils.push_api.get_vapid_public_key", {
            headers: { "Accept": "application/json" }
        });
        const data = await res.json();
        const vapidPublicKey = data.message.public_key;

        // 4. Unsubscribe any stale subscription to avoid key mismatch
        const existingSub = await registration.pushManager.getSubscription();
        if (existingSub) {
            await existingSub.unsubscribe();
        }

        // 5. Subscribe to Google FCM / Push Service
        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });

        // 6. Extract P256DH and Auth keys
        const rawP256dh = subscription.getKey("p256dh");
        const p256dh = rawP256dh ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawP256dh))) : "";
        const rawAuth = subscription.getKey("auth");
        const auth = rawAuth ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawAuth))) : "";

        // 7. Save Subscription to Backend
        await fetch("/api/method/applicant_processing.applicant_processing.utils.push_api.save_web_push_subscription", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Frappe-CSRF-Token": frappe?.csrf_token || ""
            },
            body: JSON.stringify({
                endpoint: subscription.endpoint,
                p256dh: p256dh,
                auth: auth,
                user_agent: navigator.userAgent
            })
        });

        console.log("[WebPush] Successfully subscribed and synced with server!");
        return { status: "subscribed", endpoint: subscription.endpoint };
    } catch (err) {
        console.error("[WebPush] Initialization error:", err);
        return { status: "error", error: err.message };
    }
}
```

---

### 3.2 Service Worker Implementation (`sw.js`)

```javascript
/* =========================================================================
   Applicant Processing - Background Service Worker
   ========================================================================= */

self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
    let payload = {};
    if (event.data) {
        try {
            payload = event.data.json();
        } catch (e) {
            payload = {
                title: "Applicant Processing Alert",
                body: event.data.text()
            };
        }
    }

    const title = payload.title || "Applicant Processing Alert";
    const options = {
        body: payload.body || "New pipeline update received.",
        icon: payload.icon || "/assets/frappe/images/frappe-framework-logo.png",
        badge: payload.badge || "/assets/frappe/images/frappe-framework-logo.png",
        tag: payload.tag || ("ap-alert-" + Date.now()),
        renotify: true,
        requireInteraction: true, // Keeps rectangular toast on screen until interacted with
        data: {
            url: payload.url || "/app"
        },
        actions: [
            { action: "view", title: "View Record" },
            { action: "dismiss", title: "Dismiss" }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();

    if (event.action === "dismiss") {
        return;
    }

    const targetUrl = (event.notification.data && event.notification.data.url) 
        ? event.notification.data.url 
        : "/app";

    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
            for (let client of windowClients) {
                if ("focus" in client) {
                    client.focus();
                    if (targetUrl && client.url !== targetUrl) {
                        return client.navigate(targetUrl);
                    }
                    return client;
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
```

---

## 4. Other Recent Backend Workflow APIs

### 4.1 Register Applicant (Draft ➔ Registered)
Validates mandatory registration fields (Passport, scan, photos, education, medical fitness) and transitions candidate to `Registered`.

* **Endpoint:** `POST` `/api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.register_applicant`
* **Request Body:**
  ```json
  {
    "applicant_name": "APP-00012"
  }
  ```
* **Response (Success):**
  ```json
  {
    "message": "Applicant registered successfully."
  }
  ```

---

### 4.2 Auto-Scan & Decode Passport MRZ (OCR)
Performs OCR on an uploaded image/PDF or parses raw 2-line MRZ string, auto-populating passport number, birth date, expiry, and nationality.

* **Endpoint:** `POST` `/api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.scan_and_populate_passport`
* **Request Body (Option A - Image URL):**
  ```json
  {
    "file_url": "/files/passport_scan_01.jpg",
    "applicant_name": "APP-00012"
  }
  ```
* **Request Body (Option B - Raw MRZ Lines):**
  ```json
  {
    "raw_mrz_text": "P<ETHAHMAD<<ALI<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\nEP12345678ETH9501014M3001012<<<<<<<<<<<<<<02",
    "applicant_name": "APP-00012"
  }
  ```
* **Response:**
  ```json
  {
    "message": {
      "status": "success",
      "data": {
        "passport_number": "EP1234567",
        "first_name": "AHMAD",
        "last_name": "ALI",
        "nationality": "Ethiopia",
        "date_of_birth": "1995-01-01",
        "gender": "Male",
        "passport_expiry": "2030-01-01"
      }
    }
  }
  ```

---

### 4.3 Cancel / Restore Process Pipeline
Allows authorized staff to cancel or restore an active candidate with optional audit remarks.

* **Cancel Applicant:** `POST` `/api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.cancel_applicant`
  ```json
  {
    "applicant_name": "APP-00012",
    "cancel_remarks": "Candidate withdrew application voluntarily."
  }
  ```

* **Restore Applicant:** `POST` `/api/method/applicant_processing.applicant_processing.doctype.applicant.applicant.restore_applicant`
  ```json
  {
    "applicant_name": "APP-00012"
  }
  ```

---

## 5. Automated Watchdogs & Scheduler Triggers

The backend includes cron timers that automatically dispatch Web Push notifications to officers and partner agencies:

| Scheduled Task | Cron Trigger | Purpose |
| :--- | :--- | :--- |
| `check_medical_expirations` | Daily (`0 0 * * *`) | Countdown alerts at **14d, 10d, 7d, 3d, 1d, and 0d** before GAMCA medical expires. |
| `check_pending_wakalas_biweekly` | Mon & Thu (`0 9 * * 1,4`) | Automated nudges to partner agencies for unpaid Musaned Wakalas. |
| `check_lms_missing_data_requests` | Daily (`0 8 * * *`) | Escalation alerts when requested COC/medical documents are pending > 7 days. |

---

## 6. Frontend QA & Testing Checklist

- [x] **VAPID Key Retrieval:** Verify `GET get_vapid_public_key` returns a 65-byte uncompressed P-256 base64 key.
- [x] **Browser Permission:** Click **"Enable Desktop Alerts"** and verify browser status changes to `Notification.permission === "granted"`.
- [x] **Subscription Persistence:** Verify subscription record appears in `Web Push Subscription` DocType with valid `endpoint`, `p256dh`, and `auth`.
- [x] **Closed-Tab Test:** Close all Frappe tabs, run test trigger, and verify rectangular Windows/OS notification card slides out.
- [x] **Action Click Routing:** Click the notification toast and verify it immediately opens the target Dossier or Clearance form URL.
