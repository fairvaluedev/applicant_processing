import frappe

def redesign_applicant():
    frappe.init(site="applicant-processing.localhost")
    frappe.connect()

    applicant_doctype = frappe.get_doc("DocType", "Applicant")
    
    # Define the new comprehensive fields
    new_fields = [
        {"fieldname": "personal_info_sec", "label": "Personal Information", "fieldtype": "Section Break"},
        {"fieldname": "first_name", "label": "First Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
        {"fieldname": "middle_name", "label": "Middle Name", "fieldtype": "Data"},
        {"fieldname": "last_name", "label": "Last Name", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
        {"fieldname": "col_break_personal", "fieldtype": "Column Break"},
        {"fieldname": "date_of_birth", "label": "Date of Birth", "fieldtype": "Date"},
        {"fieldname": "gender", "label": "Gender", "fieldtype": "Select", "options": "\nMale\nFemale\nOther"},
        {"fieldname": "nationality", "label": "Nationality", "fieldtype": "Data"},
        
        {"fieldname": "contact_info_sec", "label": "Contact Information", "fieldtype": "Section Break"},
        {"fieldname": "email", "label": "Email Address", "fieldtype": "Data", "options": "Email"},
        {"fieldname": "phone_number", "label": "Phone Number", "fieldtype": "Data", "reqd": 1, "in_list_view": 1},
        {"fieldname": "alternate_phone", "label": "Alternate Phone", "fieldtype": "Data"},
        {"fieldname": "col_break_contact", "fieldtype": "Column Break"},
        {"fieldname": "address_line_1", "label": "Address Line 1", "fieldtype": "Data"},
        {"fieldname": "city", "label": "City", "fieldtype": "Data"},
        {"fieldname": "country", "label": "Country", "fieldtype": "Data"},
        
        {"fieldname": "identification_sec", "label": "Identification", "fieldtype": "Section Break"},
        {"fieldname": "passport_number", "label": "Passport Number", "fieldtype": "Data"},
        {"fieldname": "passport_expiry", "label": "Passport Expiry Date", "fieldtype": "Date"},
        {"fieldname": "col_break_id", "fieldtype": "Column Break"},
        {"fieldname": "national_id", "label": "National ID Number", "fieldtype": "Data"},
        
        {"fieldname": "education_employment_sec", "label": "Education & Employment", "fieldtype": "Section Break"},
        {"fieldname": "highest_education", "label": "Highest Education Level", "fieldtype": "Select", "options": "\nHigh School\nAssociate Degree\nBachelor's Degree\nMaster's Degree\nDoctorate\nOther"},
        {"fieldname": "institution", "label": "Institution Name", "fieldtype": "Data"},
        {"fieldname": "graduation_year", "label": "Graduation Year", "fieldtype": "Int"},
        {"fieldname": "col_break_edu_emp", "fieldtype": "Column Break"},
        {"fieldname": "current_employer", "label": "Current/Last Employer", "fieldtype": "Data"},
        {"fieldname": "years_of_experience", "label": "Years of Experience", "fieldtype": "Float"},
        
        {"fieldname": "internal_info_sec", "label": "Internal Information", "fieldtype": "Section Break"},
        {"fieldname": "applicant_state", "label": "Applicant State", "fieldtype": "Select", "options": "Draft\nRegistered\nWaiting For Data\nData Complete\nCV Generated\nContract Processing\nDocumentation\nInternal Processing\nCompleted\nTicket Issued\nDeparted", "default": "Draft", "in_list_view": 1},
        {"fieldname": "registration_date", "label": "Registration Date", "fieldtype": "Date", "default": "Today"},
        {"fieldname": "col_break_internal", "fieldtype": "Column Break"},
        {"fieldname": "assigned_employee", "label": "Assigned Employee", "fieldtype": "Link", "options": "User"}
    ]
    
    # Overwrite existing fields
    applicant_doctype.fields = []
    
    for field in new_fields:
        applicant_doctype.append("fields", field)

    applicant_doctype.title_field = "first_name" 
    applicant_doctype.save(ignore_permissions=True)
    frappe.db.commit()
    print("Applicant DocType successfully redesigned.")

redesign_applicant()
