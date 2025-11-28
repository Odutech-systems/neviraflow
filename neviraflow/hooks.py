app_name = "neviraflow"
app_title = "Nevira Workflow App"
app_publisher = "Victor Mandela, Billy Adwar & Moses Njue"
app_description = "Workflow Automatin system for Nevira Minerals"
app_email = "vickadwar@gmail.com, billyfranks98@gmail.com, moses.njue@neviraminerals.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "neviraflow",
# 		"logo": "/assets/neviraflow/logo.png",
# 		"title": "Nevira Workflow App",
# 		"route": "/neviraflow",
# 		"has_permission": "neviraflow.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/neviraflow/css/neviraflow.css"
# app_include_js = "/assets/neviraflow/js/neviraflow.js"

# include js, css files in header of web template
# web_include_css = "/assets/neviraflow/css/neviraflow.css"
# web_include_js = "/assets/neviraflow/js/neviraflow.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "neviraflow/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "neviraflow/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "neviraflow.utils.jinja_methods",
# 	"filters": "neviraflow.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "neviraflow.install.before_install"
# after_install = "neviraflow.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "neviraflow.uninstall.before_uninstall"
# after_uninstall = "neviraflow.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "neviraflow.utils.before_app_install"
# after_app_install = "neviraflow.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "neviraflow.utils.before_app_uninstall"
# after_app_uninstall = "neviraflow.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "neviraflow.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"neviraflow.tasks.all"
# 	],
# 	"daily": [
# 		"neviraflow.tasks.daily"
# 	],
# 	"hourly": [
# 		"neviraflow.tasks.hourly"
# 	],
# 	"weekly": [
# 		"neviraflow.tasks.weekly"
# 	],
# 	"monthly": [
# 		"neviraflow.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "neviraflow.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "neviraflow.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "neviraflow.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["neviraflow.utils.before_request"]
# after_request = ["neviraflow.utils.after_request"]

# Job Events
# ----------
# before_job = ["neviraflow.utils.before_job"]
# after_job = ["neviraflow.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"neviraflow.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

doc_events = {
    "Quotation": {
        "before_save": "neviraflow.api.assign_export_metadata"
    },
    "Sales Order": {
        "before_validate": "neviraflow.procurement.custom_material_request.before_validate_sales_order",
        "before_submit": "neviraflow.procurement.custom_material_request.before_submit_sales_order",
        "before_save": "neviraflow.api.assign_export_metadata"
    },
    "Sales Invoice": {
        "before_validate": "neviraflow.procurement.custom_material_request.before_validate_sales_invoice",
        "before_save": [
            "neviraflow.procurement.custom_material_request.before_save_sales_invoice",
            "neviraflow.api.assign_export_metadata",
        ]
    },
    "Delivery Note": {
        "before_save": [
            "neviraflow.api.assign_export_metadata",
           # "neviraflow.api.handle_pick_list_and_qty_patch"
        ]
    },
    "Pick List": {
        #"before_save": "neviraflow.api.handle_pick_list_and_qty_patch"
    },
    "Fuel Request And Issue": {
        "validate": "neviraflow.fuel_request.validate",
        "on_submit": "neviraflow.fuel_request.on_submit"
    },
    "Weighbridge Management": {
        "after_insert": "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.auto_submit_if_ready",
        "on_update": "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.auto_submit_if_ready",
    },
    "Work Order": {
        "before_save": "neviraflow.work_order_timer.on_before_save",
        "on_submit": "neviraflow.work_order_timer.on_submit",
    },
    "Employee Checkin": {
        "after_insert": "neviraflow.attendance_handlers.after_insert_action"
    },
    "Employee": {
        "before_save": "neviraflow.employee_rate.set_daily_rate",
        "validate": "neviraflow.employee_rate.validate_employee_ctc"

    },
    "Salary Structure Assignment":{
        "before_save": "neviraflow.prorated_and_absent_salary_computations.before_submit_salary_structure_assignment"
    },
    "Salary Slip":{
        "before_save": "neviraflow.prorated_and_absent_salary_computations.compute_and_set_absent_days"
    },
}


#web_include_js = "/assets/batch_manager/js/work_order_timer.js"



doctype_js = {
    "Work Order":"public/js/work_order_timer.js",
    "Gate Pass": "public/js/gate_pass.js",
    "Quotation": "public/js/quotation.js",
    "Sales Order": "public/js/sales_order.js",
    "Sales Invoice": "public/js/sales_invoice.js",
    "Delivery Note": "public/js/delivery_note.js",
    "Purchase Invoice": "public/js/purchase_invoice.js",
    "Stock Entry": "public/js/stock_entry.js",
    "Material Request": "public/js/material_request.js",
    "Pick List": "public/js/pick_list.js",
    "Stock Reconciliation": "public/js/stock_reconciliation.js",
    "Weighbridge Management": "neviraflow/weighbridge/doctype/weighbridge_management/weighbridge_management.js"
}



app_include_js = "/assets/neviraflow/js/bag_tonne_logic.js"


scheduler_events = {
    "cron": {
        "*/5 * * * *": ["frappe.email.queue.flush"],
        #"0 10 * * *" : ["neviraflow.attendance_absentee_job.mark_absentees"]
    },
}
