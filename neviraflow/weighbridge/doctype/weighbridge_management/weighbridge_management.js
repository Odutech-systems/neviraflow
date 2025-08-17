// Copyright (c) 2025, Victor Mandela
// For license information, please see license.txt

frappe.ui.form.on("Weighbridge Management", {
  refresh(frm) {
    handle_button_display(frm);
    handle_field_visibility(frm);
    handle_table_visibility(frm);
    handle_stock_entry_visibility(frm);

    // Session badge for multi-weighing (avoid piling duplicates)
    frm.dashboard.clear_headline();
    if (frm.doc.has_multiple_weights && frm.doc.total_weighings_expected) {
      const current = frm.doc.current_weighing_no || 1;
      const total = frm.doc.total_weighings_expected;
      frm.dashboard.add_comment(`Weighing ${current} / ${total}`, "blue", true);
    }

    // Lock core fields after capture or when outbound linked
    const locked = frm.doc.weighing_status === "Completed" || !!frm.doc.stock_entry_reference;
    if (locked) {
      ["item_type", "first_weight", "second_weight", "quarry_from", "work_order"].forEach((f) =>
        frm.set_df_property(f, "read_only", 1)
      );
    }
  },

  item_type(frm) {
    handle_field_visibility(frm);
    handle_table_visibility(frm);
  },

  first_weight(frm) {
    if (frm.doc.first_weight && !frm.doc.second_weight) {
      frm.set_value("weighing_status", "Awaiting Second Weight");
    } else if (!frm.doc.first_weight) {
      frm.set_value("weighing_status", "Pending First Weight");
    } else if (frm.doc.first_weight && frm.doc.second_weight) {
      const fw = flt(frm.doc.first_weight);
      const sw = flt(frm.doc.second_weight);
      if (sw > fw) {
        frm.set_value("final_weight", sw - fw);
        frm.set_value("weighing_status", "Ready for Capture");
      }
    }
  },

  second_weight(frm) {
    if (frm.doc.first_weight && frm.doc.second_weight) {
      const fw = flt(frm.doc.first_weight);
      const sw = flt(frm.doc.second_weight);
      if (sw > fw) {
        frm.set_value("final_weight", sw - fw);
        frm.set_value("weighing_status", "Ready for Capture");
      } else {
        frappe.msgprint("Second weight must be greater than first weight.");
        frm.set_value("second_weight", null);
      }
    }
  }
});

function handle_button_display(frm) {
  const { doc } = frm;

  const eligible_types = [
    "Raw Materials",
    "Raw Materials - Production",
    "Partner Production",
    "Inter-Company Transfer",
    "Finished Goods",
  ];

  const ready_for_capture =
    doc.docstatus === 1 &&
    eligible_types.includes(doc.item_type) &&
    doc.weighing_status === "Ready for Capture";

  // Add primary action only when eligible
  if (ready_for_capture) {
    frm.add_custom_button("Capture Return Info", function () {
      if (!doc.second_weight) {
        frappe.msgprint("Second weight is required before capturing.");
        return;
      }

      const dialog = new frappe.ui.Dialog({
        title: "Capture Return Info",
        fields: [
          {
            label: "Material Type",
            fieldname: "item_type",
            fieldtype: "Select",
            options: eligible_types.join("\n"),
            default: doc.item_type,
            reqd: 1,
            onchange: () => toggle_dynamic_fields(dialog, dialog.get_value("item_type") || doc.item_type),
          },
          {
            label: "Second Weight (kg)",
            fieldname: "second_weight_display",
            fieldtype: "Float",
            default: doc.second_weight || null,
            read_only: 1,
          },
          // Item selection + readable name
          {
            label: "Item Code",
            fieldname: "item_code",
            fieldtype: "Link",
            options: "Item",
          },
          {
            label: "Item Name",
            fieldname: "item_name_display",
            fieldtype: "Data",
            read_only: 1,
          },
          // Quarry for Raw Materials
          {
            label: "Quarry From",
            fieldname: "quarry_from",
            fieldtype: "Link",
            options: "Quarry Management",
          },
          // Customer selection + readable name
          {
            label: "Customer",
            fieldname: "customer_name",
            fieldtype: "Link",
            options: "Customer",
          },
          {
            label: "Customer Name",
            fieldname: "customer_name_display",
            fieldtype: "Data",
            read_only: 1,
          },
          // Partner Production fields
          {
            label: "Partner Description",
            fieldname: "partner_description",
            fieldtype: "Data",
          },
          {
            label: "Item Description",
            fieldname: "item_description",
            fieldtype: "Data",
          },
        ],
        primary_action_label: "Submit",
        primary_action(values) {
          const chosen_type = values.item_type || doc.item_type;

          // Build method + args per type (send only expected params)
          const route = (() => {
            if (chosen_type === "Raw Materials") {
              if (!values.item_code || !values.quarry_from) {
                frappe.msgprint("Item Code and Quarry From are required for Raw Materials.");
                return null;
              }
              return {
                method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.capture_raw_material_return",
                args: {
                  docname: doc.name,
                  second_weight: doc.second_weight,
                  item_code: values.item_code,
                  quarry_from: values.quarry_from,
                },
              };
            }

            if (chosen_type === "Raw Materials - Production") {
              if (!values.item_code) {
                frappe.msgprint("Item Code is required for Production.");
                return null;
              }
              return {
                method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.capture_production_material_return",
                args: {
                  docname: doc.name,
                  second_weight: doc.second_weight,
                  item_code: values.item_code,
                  item_type: chosen_type,
                },
              };
            }

            if (chosen_type === "Partner Production") {
              if (!values.partner_description || !values.item_description) {
                frappe.msgprint("Partner and Item Description are required.");
                return null;
              }
              const partner_items = [
                {
                  partner_description: values.partner_description,
                  item_description: values.item_description,
                  first_weight: doc.first_weight || 0,
                  second_weight: doc.second_weight,
                  quantity: (doc.second_weight - (doc.first_weight || 0)) / 1000,
                },
              ];
              return {
                method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.capture_partner_production",
                args: {
                  docname: doc.name,
                  partner_items: JSON.stringify(partner_items),
                },
              };
            }

            if (chosen_type === "Inter-Company Transfer") {
              if (!values.item_code) {
                frappe.msgprint("Item Code is required for Inter-Company Transfer.");
                return null;
              }
              return {
                method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.capture_inter_company_transfer",
                args: {
                  docname: doc.name,
                  second_weight: doc.second_weight,
                  item_code: values.item_code,
                  item_type: chosen_type,
                },
              };
            }

            if (chosen_type === "Finished Goods") {
              if (!values.item_code || !values.customer_name) {
                frappe.msgprint("Item and Customer are required for Finished Goods.");
                return null;
              }
              return {
                method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.capture_customer_transfer",
                args: {
                  docname: doc.name,
                  second_weight: doc.second_weight,
                  item_code: values.item_code,
                  customer_name: values.customer_name,
                  item_type: chosen_type,
                },
              };
            }

            frappe.msgprint("Unsupported material type.");
            return null;
          })();

          if (!route) return;

          frappe.call({
            method: route.method,
            args: route.args,
            freeze: true,
            freeze_message: __("Capturing..."),
            callback: function () {
              frappe.msgprint("Capture successful");
              dialog.hide();
              frm.set_value("item_type", chosen_type);
              frm.reload_doc();
            },
          });
        },
      });

      // Dynamic filters and name displays
      dialog.fields_dict.item_code.get_query = () => {
        const type = dialog.get_value("item_type") || frm.doc.item_type;
        const group = ["Inter-Company Transfer", "Finished Goods"].includes(type)
          ? "Finished Goods-BULK"
          : "Raw Materials - BULK";
        return { filters: { item_group: group } };
      };

      // Populate Item Name when Item Code changes
      setTimeout(() => {
        const it = dialog.fields_dict.item_code;
        if (it && it.$input) {
          it.$input.on("change", async () => {
            const code = dialog.get_value("item_code");
            if (code) {
              const r = await frappe.db.get_value("Item", code, "item_name");
              dialog.set_value("item_name_display", r?.message?.item_name || "");
            } else {
              dialog.set_value("item_name_display", "");
            }
          });
        }
      }, 0);

      // Populate Customer Name when Customer changes
      setTimeout(() => {
        const cn = dialog.fields_dict.customer_name;
        if (cn && cn.$input) {
          cn.$input.on("change", async () => {
            const cust = dialog.get_value("customer_name");
            if (cust) {
              const r = await frappe.db.get_value("Customer", cust, "customer_name");
              dialog.set_value("customer_name_display", r?.message?.customer_name || "");
            } else {
              dialog.set_value("customer_name_display", "");
            }
          });
        }
      }, 0);

      // Initial toggle based on default selection
      toggle_dynamic_fields(dialog, dialog.get_value("item_type") || doc.item_type);

      dialog.show();
    });
  }

  // Confirm buttons
  if (doc.docstatus === 1 && doc.item_type === "Raw Materials" && doc.weighing_status === "Completed") {
    frm.add_custom_button("Confirm RM Receipt", () => {
      frappe.call({
        method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.confirm_rm_receipt",
        args: { docname: doc.name },
        callback: () => {
          frappe.msgprint("Stock Entry Created and Confirmed");
          frm.reload_doc();
        },
      });
    });
  }

  if (doc.docstatus === 1 && doc.item_type === "Raw Materials - Production" && doc.weighing_status === "Completed") {
    frm.add_custom_button("Confirm Production Transfer", () => {
      frappe.prompt(
        [
          {
            label: "Work Order",
            fieldname: "work_order",
            fieldtype: "Link",
            options: "Work Order",
            reqd: 1,
          },
        ],
        (values) => {
          frappe.call({
            method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.confirm_production_transfer",
            args: { docname: doc.name, work_order: values.work_order },
            callback: () => {
              frappe.msgprint("Stock Entry Created and Confirmed");
              frm.reload_doc();
            },
          });
        },
        "Link Work Order",
        "Confirm"
      );
    });
  }
}

function toggle_dynamic_fields(dialog, type) {
  const show_fields = {
    "Raw Materials": ["item_code", "item_name_display", "quarry_from", "second_weight_display"],
    "Raw Materials - Production": ["item_code", "item_name_display", "second_weight_display"],
    "Partner Production": ["partner_description", "item_description", "second_weight_display"],
    "Inter-Company Transfer": ["item_code", "item_name_display", "second_weight_display"],
    "Finished Goods": ["item_code", "item_name_display", "customer_name", "customer_name_display", "second_weight_display"],
  };

  const all_fields = [
    "second_weight_display",
    "item_code",
    "item_name_display",
    "quarry_from",
    "customer_name",
    "customer_name_display",
    "partner_description",
    "item_description",
  ];

  const setVisible = (fname, visible) => {
    const df = dialog.get_field(fname);
    if (!df) return;
    if (typeof dialog.toggle_display === "function") {
      dialog.toggle_display(fname, visible);
      return;
    }
    if (typeof df.toggle === "function") {
      df.toggle(visible);
      return;
    }
    dialog.set_df_property(fname, "hidden", !visible);
    dialog.refresh_field(fname);
  };

  all_fields.forEach((f) => setVisible(f, false));
  (show_fields[type] || []).forEach((f) => setVisible(f, true));
}


function handle_field_visibility(frm) {
  const type = frm.doc.item_type;
  frm.set_df_property("delivery_to", "hidden", type !== "Raw Materials");
  frm.set_df_property("quarry_from", "hidden", type !== "Raw Materials");
  frm.set_df_property("milling_machine", "hidden", type !== "Raw Materials - Production");
  frm.set_df_property("work_order", "hidden", type !== "Raw Materials - Production");
}

function handle_table_visibility(frm) {
  const type = frm.doc.item_type;
  frm.toggle_display("item_details", ["Raw Materials", "Raw Materials - Production"].includes(type));
  frm.toggle_display("partner_item_list", type === "Partner Production");
  frm.toggle_display("company_transfer", type === "Inter-Company Transfer");
  frm.toggle_display("customer_item_description", type === "Finished Goods");
}

function handle_stock_entry_visibility(frm) {
  frm.toggle_display("stock_entry_reference", Boolean(frm.doc.stock_entry_reference));
}
