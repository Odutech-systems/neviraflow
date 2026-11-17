frappe.ui.form.on("Loading Schedule",{
    onload(frm){
        apply_bag_tonne_logic("First Trip");
        apply_bag_tonne_logic("Second Trip");
        apply_bag_tonne_logic("After Midnight Trip");
    }
});