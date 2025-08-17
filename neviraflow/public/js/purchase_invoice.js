frappe.ui.form.on("Purchase Invoice", {
    onload(frm) {
      apply_bag_tonne_logic("Purchase Invoice Item");
    }
  });
  