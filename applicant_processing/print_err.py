import frappe
def execute():
    errs = frappe.db.get_all('Error Log', fields=['method', 'error'], limit=3, order_by='creation desc')
    for err in errs:
        print("====== ERROR START ======")
        print("METHOD:", err.method)
        print(err.error)
        print("====== ERROR END ======")
