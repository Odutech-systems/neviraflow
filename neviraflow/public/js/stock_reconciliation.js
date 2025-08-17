frappe.ui.form.on("Stock Reconciliation", {
    onload(frm) {
      apply_bag_tonne_logic("Stock Reconciliation Item");
    }
  });
  