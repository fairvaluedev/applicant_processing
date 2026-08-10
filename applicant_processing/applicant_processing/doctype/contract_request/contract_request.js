// Copyright (c) 2026, Admin and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Request", {
    refresh(frm) {
        frm.trigger("source_type");
    },
    
    source_type(frm) {
        if (frm.doc.source_type === "CV Record") {
            frm.set_df_property("applicant", "read_only", 1);
        } else {
            frm.set_df_property("applicant", "read_only", 0);
        }
    },

    cv_reference(frm) {
        if (frm.doc.source_type !== "CV Record") return;
        
        if (frm.doc.cv_reference) {
            frappe.db.get_value("CV Record", frm.doc.cv_reference, [
                "applicant", "first_name", "middle_name", "last_name",
                "date_of_birth", "gender", "nationality", "email", "phone_number",
                "passport_number", "passport_expiry", "national_id",
                "highest_education", "institution", "graduation_year"
            ], function(value) {
                if (!value) return;
                Object.keys(value).forEach(function(field) {
                    frm.set_value(field, value[field]);
                });
            });
        } else {
            frm.set_value("applicant", null);
        }
    },
    
    applicant(frm) {
        if (frm.doc.source_type !== "Document Received") return;
        
        if (frm.doc.applicant) {
            frappe.db.get_value("Applicant", frm.doc.applicant, [
                "first_name", "middle_name", "last_name",
                "date_of_birth", "gender", "nationality", "email", "phone_number",
                "passport_number", "passport_expiry", "national_id",
                "highest_education", "institution", "graduation_year"
            ], function(value) {
                if (!value) return;
                Object.keys(value).forEach(function(field) {
                    frm.set_value(field, value[field]);
                });
            });
        }
    }
});
