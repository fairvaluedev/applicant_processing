import frappe

def run_tests():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()

    # 1. Ensure a Mandatory Data Request Type exists
    if not frappe.db.exists("Data Request Type", "Test Medical Certificate"):
        frappe.get_doc({
            "doctype": "Data Request Type",
            "data_request_name": "Test Medical Certificate",
            "mandatory": 1,
            "applicable_stage": "Registration"
        }).insert(ignore_permissions=True)
        print("Created Data Request Type: Test Medical Certificate")

    # 2. Create a dummy Applicant
    applicant = frappe.get_doc({
        "doctype": "Applicant",
        "first_name": "John",
        "last_name": "Doe",
        "phone_number": "+123456789"
    })
    applicant.insert(ignore_permissions=True)
    
    print(f"Created Applicant: {applicant.name}")
    print(f"Initial State should be 'Waiting For Data'. Actual: {applicant.applicant_state}")
    
    if applicant.applicant_state != "Waiting For Data":
        print("FAIL: Applicant state did not advance to Waiting For Data")
        return

    # 3. Check for generated Data Requests
    requests = frappe.get_all("Data Request", filters={"applicant": applicant.name}, fields=["name", "status"])
    print(f"Found {len(requests)} Data Requests for {applicant.name}")
    if len(requests) == 0:
        print("FAIL: No Data Requests generated")
        return
        
    # 4. Complete the data requests to trigger the state change
    for req in requests:
        doc = frappe.get_doc("Data Request", req.name)
        doc.status = "Completed"
        doc.save(ignore_permissions=True)
        print(f"Completed Data Request {req.name}")
        
    # 5. Check if Applicant transitioned
    applicant.reload()
    print(f"Final Applicant State should be 'Data Complete'. Actual: {applicant.applicant_state}")
    
    if applicant.applicant_state == "Data Complete":
        print("SUCCESS! Verification passed.")
    else:
        print("FAIL: State did not transition to Data Complete")

    # Cleanup
    frappe.db.rollback() # Rollback to keep database clean
    print("Test finished, DB rolled back.")

run_tests()
