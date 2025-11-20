// Copyright (c) 2025, BILLY ADWAR and contributors
// For license information, please see license.txt

frappe.ui.form.on("Prorated Salary Structure Assignment", {
    refresh: function(frm){
        // Add custom button to get the employees
        frm.add_custom_button(__("Get Employees"), function(){
            if(!frm.doc.start_date || !frm.doc.to_date){
                frappe.msgprint(__("Please select the start date and to date first"));
                return;
            }
            frm.call('get_employees_based_on_dates').then(r => {
                if(r.message){ 
                    frm.refresh_field('prorated_employees')
                }
            });
        });

        // Add buttons to view assignments
        if(frm.doc_status === 1){
            frm.add_custom_button(__("View Assignments"), function(){
                frm.call('get_created_assignments').then(r => {
                    if(r.message && r.message.length > 0){
                        frappe.route_options = {
                            "name" : ["in", r.message]
                        };
                        frappe.set_route("List","Salary Structure Assignment");
                    } 
                    else {
                        frappe.msgprint(__("No assignments found"));
                    }
                });
            });
        }
    },

    start_date: function(frm){
        if(frm.doc.start_date && frm.doc.to_date){
            frm.trigger('validate_dates');
        }
    },

    to_date: function(frm){
        if(frm.doc.start_date && frm.doc.to_date){
            frm.trigger('validate_dates');
        }
    },

    validate_dates: function(frm){
        if(frm.doc.start_date > frm.doc.to_date){
            frappe.msgprint(__("To date cannot be before start date"));
            frm.set_value('to_date','');
        }
    }
});

