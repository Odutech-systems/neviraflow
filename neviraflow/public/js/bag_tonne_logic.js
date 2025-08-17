// -------------------------------
// Bag ↔ Tonne ↔ Rate Logic
// -------------------------------
// Shared Logic: Auto-calculate Bags (qty) from Tonnes or Bags Input + rate from ERPNext's default price per tonne logic

const apply_bag_tonne_logic = function (doctype) {
  const roundTo = (value, decimals) => {
    return parseFloat(value.toFixed(decimals));
  };

  frappe.ui.form.on(doctype, {
    item_code(frm, cdt, cdn) {
      const row = locals[cdt][cdn];
      frappe.model.set_value(cdt, cdn, "bags_input", null);
      frappe.model.set_value(cdt, cdn, "tonnes_input", null);
      frappe.model.set_value(cdt, cdn, "price_per_tonne", null);

      // Fetch the currency of the price list
      frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "Price List",
          filters: { name: frm.doc.selling_price_list },
          fieldname: ["currency"]
        },
        callback: function (currency_res) {
          const price_list_currency = currency_res.message?.currency || "";

          // Fetch price per tonne from the price list
          frappe.call({
            method: "frappe.client.get_value",
            args: {
              doctype: "Item Price",
              filters: {
                item_code: row.item_code,
                selling: 1,
                price_list: frm.doc.selling_price_list
              },
              fieldname: ["price_list_rate"]
            },
            callback: function (res) {
              if (res.message && res.message.price_list_rate) {
                const price_per_tonne = res.message.price_list_rate;
                row._frozen_price_per_tonne = price_per_tonne;
                frappe.model.set_value(cdt, cdn, "price_per_tonne", price_per_tonne);

                frappe.db.get_value("Item", row.item_code, "weight_per_unit", function (r) {
                  const weight = r.weight_per_unit;
                  if (weight && price_per_tonne) {
                    const rate_per_bag = price_per_tonne * weight;
                    row._default_rate_per_bag = rate_per_bag; // defer setting rate until quantity is provided
                    frappe.model.set_value(cdt, cdn, "currency", price_list_currency);
                  }
                });
              }
            }
          });
        }
      });
    },

    tonnes_input(frm, cdt, cdn) {
      const row = locals[cdt][cdn];
      if (!row.tonnes_input || !row.item_code) return;

      frappe.db.get_value("Item", row.item_code, ["weight_per_unit", "stock_uom"], function (r) {
        const weight = r.weight_per_unit;
        const stock_uom = r.stock_uom;

        const tonnes = roundTo(row.tonnes_input, 2);
        let bags;

        if (stock_uom === "Bag - 1 Tonne") {
          bags = tonnes;
        } else {
          if (!weight) return;
          bags = Math.round(tonnes / weight);
        }

        frappe.model.set_value(cdt, cdn, "qty", bags);
        frappe.model.set_value(cdt, cdn, "bags_input", bags);
        frappe.model.set_value(cdt, cdn, "tonnes_input", tonnes);

        // Additional: set picked_qty if it exists
        if ("picked_qty" in row) {
          frappe.model.set_value(cdt, cdn, "picked_qty", bags);
        }

        let rate;
        if (stock_uom === "Bag - 1 Tonne") {
          rate = row._frozen_price_per_tonne;
        } else if (weight && row._frozen_price_per_tonne) {
          rate = row._frozen_price_per_tonne * weight;
        } else if (row._default_rate_per_bag) {
          rate = row._default_rate_per_bag;
        }

        if (rate) {
          frappe.model.set_value(cdt, cdn, "rate", rate);
          frappe.model.set_value(cdt, cdn, "amount", (bags || 0) * rate);
        }
      });
    },

    bags_input(frm, cdt, cdn) {
      const row = locals[cdt][cdn];
      if (!row.bags_input || !row.item_code) return;

      frappe.db.get_value("Item", row.item_code, ["weight_per_unit", "stock_uom"], function (r) {
        const weight = r.weight_per_unit;
        const stock_uom = r.stock_uom;

        const bags = parseInt(row.bags_input, 10);
        let tonnes;

        if (stock_uom === "Bag - 1 Tonne") {
          tonnes = bags;
        } else {
          if (!weight) return;
          tonnes = roundTo(bags * weight, 2);
        }

        frappe.model.set_value(cdt, cdn, "bags_input", bags);
        frappe.model.set_value(cdt, cdn, "tonnes_input", tonnes);
        frappe.model.set_value(cdt, cdn, "qty", bags);

        // Additional: set picked_qty if it exists
        if ("picked_qty" in row) {
          frappe.model.set_value(cdt, cdn, "picked_qty", bags);
        }

        let rate;
        if (stock_uom === "Bag - 1 Tonne") {
          rate = row._frozen_price_per_tonne;
        } else if (weight && row._frozen_price_per_tonne) {
          rate = row._frozen_price_per_tonne * weight;
        } else if (row._default_rate_per_bag) {
          rate = row._default_rate_per_bag;
        }

        if (rate) {
          frappe.model.set_value(cdt, cdn, "rate", rate);
          frappe.model.set_value(cdt, cdn, "amount", (bags || 0) * rate);
        }
      });
    }
  });
};


// -------------------------------
// Territory-Based Tax Logic
// -------------------------------
const apply_territory_tax_logic = function (parent_doctype) {
  frappe.ui.form.on(parent_doctype, {
    onload(frm) {
      if (frm.doc.customer && !frm.doc.taxes_and_charges) {
        set_tax_based_on_territory(frm);
      }
    },
    customer(frm) {
      if (frm.doc.customer) {
        set_tax_based_on_territory(frm);
      }
    }
  });

  function set_tax_based_on_territory(frm) {
    frappe.db.get_value("Customer", frm.doc.customer, "territory").then(r => {
      const territory = r.message.territory;
      if (!territory) return;

      if (territory === "Kenya") {
        frm.set_value("taxes_and_charges", "Kenya Tax - NML");
      } else if (territory === "Rest Of The World") {
        frm.set_value("taxes_and_charges", "Rest of World Tax - NML");
      }
    });
  }
};


// --------------------------------------------------
// Transport Charges Logic
// --------------------------------------------------
const apply_transport_logic = function (doctype) {
  frappe.ui.form.on(doctype, {
    transport_charged: async function (frm) {
      const transport_item_code = "SRV-001";

      if (!frm.doc.transport_charged) {
        frm.doc.items = frm.doc.items.filter(i => i.item_code !== transport_item_code);
        frm.refresh_field('items');
        return;
      }

      const already_added = frm.doc.items.find(i => i.item_code === transport_item_code);
      if (already_added) return;

      const { message: rateInfo } = await frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "Item Price",
          filters: {
            item_code: transport_item_code,
            price_list: frm.doc.selling_price_list
          },
          fieldname: ["price_list_rate"]
        }
      });

      if (rateInfo && rateInfo.price_list_rate) {
        frm.add_child("items", {
          item_code: transport_item_code,
          item_name: "TRANSPORT",
          rate: rateInfo.price_list_rate,
          qty: 1,
          uom: "Nos"
        });
        frm.refresh_field("items");
      } else {
        frappe.msgprint("Transport charge not found in price list.");
      }
    }
  });
};
