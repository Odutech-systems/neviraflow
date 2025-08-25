// Copyright (c) 2025, Victor Mandela
// License: see license.txt

frappe.ui.form.on("Weighbridge Management", {
  refresh(frm) {
    handle_field_visibility(frm);
    handle_table_visibility(frm);
    handle_stock_entry_visibility(frm);
    lock_fields_if_final(frm);
    handle_button_display(frm);

    frm.dashboard.clear_headline();
    if (frm.doc.has_multiple_weights && frm.doc.total_weighings_expected) {
      const current = frm.doc.current_weighing_no || 1;
      const total = frm.doc.total_weighings_expected;
      frm.dashboard.add_comment(`Weighing ${current} / ${total}`, "blue", true);
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
      update_weighing_status_based_on_type(frm);
    }
  },

  second_weight(frm) {
    if (frm.doc.first_weight && frm.doc.second_weight) {
      const sw = flt(frm.doc.second_weight);
      if (sw > 0) {
        update_weighing_status_based_on_type(frm);
      } else {
        frappe.msgprint("Second weight must be greater than zero.");
        frm.set_value("second_weight", null);
      }
    }
  },
});

function update_weighing_status_based_on_type(frm) {
  const fw = flt(frm.doc.first_weight);
  const sw = flt(frm.doc.second_weight);
  const final = Math.abs(sw - fw);
  frm.set_value("final_weight", final);
  frm.set_value("weighing_status", "Ready for Capture");
}

function handle_button_display(frm) {
  frm.clear_custom_buttons();
  const { doc } = frm;
  const type = doc.item_type;
  const status = doc.weighing_status;
  const has_items = has_child_table_data(doc);

  const eligible_types = [
    "Raw Materials",
    "Raw Materials - Production",
    "Partner Production",
    "Inter-Company Transfer",
    "Finished Goods",
    "Purchased Materials",
  ];

  const can_capture =
    doc.docstatus === 1 &&
    eligible_types.includes(type) &&
    !doc.stock_entry_reference &&
    status === "Ready for Capture";

  const can_confirm =
    doc.docstatus === 1 &&
    status === "Pending Confirmation" &&
    !doc.stock_entry_reference &&
    has_items;

  if (can_capture && !has_items) {
    frm.add_custom_button("Capture Return Info", function () {
      open_capture_dialog(frm);
    });
  }

  if (can_confirm && type === "Raw Materials") {
    frm.add_custom_button("Confirm RM Receipt", function () {
      frappe.call({
        method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.confirm_rm_receipt",
        args: { docname: doc.name },
        callback: () => frm.reload_doc(),
      });
    });
  }

  if (can_confirm && type === "Raw Materials - Production") {
    frm.add_custom_button("Confirm Production Transfer", function () {
      const dialog = new frappe.ui.Dialog({
        title: "Confirm Work Order",
        fields: [
          {
            label: "Work Order",
            fieldname: "work_order",
            fieldtype: "Link",
            options: "Work Order",
            reqd: 1,
          },
        ],
        primary_action_label: "Confirm",
        primary_action(values) {
          frappe.call({
            method: "neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.confirm_production_transfer",
            args: { docname: doc.name, work_order: values.work_order },
            callback: () => {
              dialog.hide();
              frm.reload_doc();
            },
          });
        },
      });
      dialog.show();
    });
  }
}

function lock_fields_if_final(frm) {
  const { doc } = frm;
  const is_locked =
    doc.stock_entry_reference ||
    doc.weighing_status === "Completed" ||
    (["Partner Production", "Purchased Materials", "Finished Goods", "Inter-Company Transfer"].includes(doc.item_type) &&
      has_child_table_data(doc));

  if (is_locked) {
    const lock_fields = ["item_type", "first_weight", "second_weight", "quarry_from", "work_order"];
    lock_fields.forEach((f) => frm.set_df_property(f, "read_only", 1));
  }
}

function has_child_table_data(doc) {
  return (
    (doc.item_details && doc.item_details.length > 0) ||
    (doc.partner_item_list && doc.partner_item_list.length > 0) ||
    (doc.company_transfer && doc.company_transfer.length > 0) ||
    (doc.customer_item_description && doc.customer_item_description.length > 0) ||
    (doc.purchased_item_list && doc.purchased_item_list.length > 0)
  );
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
  frm.toggle_display("purchased_item_list", type === "Purchased Materials");
}

function handle_stock_entry_visibility(frm) {
  frm.toggle_display("stock_entry_reference", Boolean(frm.doc.stock_entry_reference));
}

function open_capture_dialog(frm) {
  const { doc } = frm;
  const eligible_types = [
    "Raw Materials",
    "Raw Materials - Production",
    "Partner Production",
    "Inter-Company Transfer",
    "Finished Goods",
    "Purchased Materials",
  ];

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
      {
        label: "Quarry From",
        fieldname: "quarry_from",
        fieldtype: "Link",
        options: "Quarry Management",
      },
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

      const method_map = {
        "Raw Materials": "capture_raw_material_return",
        "Raw Materials - Production": "capture_production_material_return",
        "Purchased Materials": "capture_purchased_material",
        "Inter-Company Transfer": "capture_inter_company_transfer",
        "Finished Goods": "capture_finished_goods",
        "Partner Production": "capture_partner_production",
      };

      const method_name = method_map[chosen_type];
      if (!method_name) {
        frappe.msgprint("Unsupported material type.");
        return;
      }

      // Build args per type
      let args = { docname: doc.name };

      if (chosen_type === "Partner Production") {
        // Pack a single dialog row into array for API
        const partner_items = [
          {
            partner_description: values.partner_description || "",
            item_description: values.item_description || "",
            // quantity omitted; backend will default from final_weight in tonnes
          },
        ];
        args.partner_items = JSON.stringify(partner_items);
      } else {
        // Types using item_code + second_weight
        args.second_weight = doc.second_weight;
        args.item_code = values.item_code || null;

        if (chosen_type === "Raw Materials") {
          args.quarry_from = values.quarry_from || null;
        }
        if (chosen_type === "Raw Materials - Production") {
          args.item_type = chosen_type;
        }
        if (chosen_type === "Finished Goods") {
          // IMPORTANT: pass the Customer LINK (code/id), not the human name
          args.customer = values.customer_name || null;
        }
      }

      frappe.call({
        method: `neviraflow.weighbridge.doctype.weighbridge_management.weighbridge_management.${method_name}`,
        args,
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

// Populate display fields when link fields change or are selected from dropdown
setTimeout(() => {
  const itemInput = dialog.get_input("item_code");
  if (itemInput) {
    const handler = async () => {
      const code = dialog.get_value("item_code");
      if (code) {
        const r = await frappe.db.get_value("Item", code, "item_name");
        dialog.set_value("item_name_display", r?.message?.item_name || "");
      } else {
        dialog.set_value("item_name_display", "");
      }
    };
    // Catch both typing+blur and awesomplete selection
    itemInput.on("change", handler);
    itemInput.on("awesomplete-selectcomplete", handler);
  }

  const custInput = dialog.get_input("customer_name");
  if (custInput) {
    const handler = async () => {
      const code = dialog.get_value("customer_name"); // LINK code
      if (code) {
        const r = await frappe.db.get_value("Customer", code, "customer_name");
        dialog.set_value("customer_name_display", r?.message?.customer_name || "");
      } else {
        dialog.set_value("customer_name_display", "");
      }
    };
    custInput.on("change", handler);
    custInput.on("awesomplete-selectcomplete", handler);
  }
}, 0);


  toggle_dynamic_fields(dialog, dialog.get_value("item_type") || doc.item_type);
  dialog.show();
}

function toggle_dynamic_fields(dialog, type) {
  const visible_fields = {
    "Raw Materials": ["item_code", "item_name_display", "quarry_from", "second_weight_display"],
    "Raw Materials - Production": ["item_code", "item_name_display", "second_weight_display"],
    "Partner Production": ["partner_description", "item_description", "second_weight_display"],
    "Inter-Company Transfer": ["item_code", "item_name_display", "second_weight_display"],
    "Finished Goods": ["item_code", "item_name_display", "customer_name", "customer_name_display", "second_weight_display"],
    "Purchased Materials": ["item_code", "item_name_display", "second_weight_display"],
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

  all_fields.forEach((f) => dialog.set_df_property(f, "hidden", true));
  (visible_fields[type] || []).forEach((f) => dialog.set_df_property(f, "hidden", false));
  dialog.refresh();
}
