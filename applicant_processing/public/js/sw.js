/* =========================================================================
   Applicant Processing - Chrome & Desktop Web Push Service Worker
   ========================================================================= */

self.addEventListener("install", (event) => {
    // Activate worker immediately
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    // Become available to all clients immediately
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
        body: payload.body || "You have a new processing alert.",
        icon: payload.icon || "/assets/frappe/images/frappe-framework-logo.png",
        badge: payload.badge || "/assets/frappe/images/frappe-framework-logo.png",
        tag: payload.tag || ("ap-push-" + Date.now()),
        renotify: true,
        requireInteraction: true, // Keeps rectangular popup visible until clicked or dismissed
        data: {
            url: payload.url || "/app",
            dateOfArrival: Date.now(),
            primaryKey: payload.primaryKey || 1
        },
        actions: [
            {
                action: "open_dossier",
                title: "View Record"
            },
            {
                action: "dismiss",
                title: "Dismiss"
            }
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
            // If already open, focus it and navigate
            for (let client of windowClients) {
                if ("focus" in client) {
                    client.focus();
                    if (targetUrl && client.url !== targetUrl) {
                        return client.navigate(targetUrl);
                    }
                    return client;
                }
            }
            // If no window is open, open a new window
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
