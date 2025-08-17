frappe.ui.form.on("Material Request", {
    onload(frm) {
      apply_bag_tonne_logic("Material Request Item");
    }
  });
  