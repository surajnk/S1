odoo.define('mrp_enhancement.Many2OneBarcodeLot', function (require) {
"use strict";

var relational_fields = require('web.relational_fields');
var fieldRegistry = require('web.field_registry');

var FieldMany2One = relational_fields.FieldMany2One;

var FieldMany2OneBarcodeLot = FieldMany2One.extend({
    events: _.extend({}, FieldMany2One.prototype.events, {
        'keydown input': '_onLotBarcodeKeydown',
        'focus input': '_onBarcodeFieldFocus',
    }),

    _onBarcodeFieldFocus: function (ev) {        // <-- 2. method, add this
        this.$input.select();
    },

    _onLotBarcodeKeydown: function (ev) {
        if (ev.which !== $.ui.keyCode.ENTER) {
            return; // let the field's own 'input' event handle normal typing
        }
        var value = this.$input.val().trim();
        if (!value) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this._exactLotSearch(value);
    },

    _exactLotSearch: function (value) {
        var self = this;
        var productId = this.record.data.product_id && this.record.data.product_id.res_id;
        var domain = productId ? [['product_id', '=', productId]] : [];
        return this._rpc({
            model: 'stock.production.lot',
            method: 'name_search',
            kwargs: { name: value, args: domain, operator: '=', limit: 2 },
        }).then(function (results) {
            if (results.length === 1) {
                self.reinitialize({ id: results[0][0], display_name: results[0][1] });
                self._setValue({ id: results[0][0], display_name: results[0][1] });
            } else if (results.length === 0) {
                self.do_notify(_.str.sprintf("No lot found matching '%s'", value));
            }
            // 2+ matches: leave for manual resolution
        });
    },
});

var FieldMany2OneBarcodeLocation = FieldMany2One.extend({
    start: function () {
        var res = this._super.apply(this, arguments);
        var self = this;
        this.$el[0].addEventListener('keydown', function (ev) {
            if (ev.target !== self.$input[0]) {
                return;
            }
            if (ev.which !== $.ui.keyCode.ENTER && ev.which !== $.ui.keyCode.TAB) {
                return;
            }
            var value = self.$input.val().trim();
            if (!value) {
                return;
            }
            if (ev.which === $.ui.keyCode.ENTER) {
                ev.preventDefault();
                ev.stopPropagation();
            }
            self._exactLocationSearch(value);
        }, true);
        return res;
    },
    events: _.extend({}, FieldMany2One.prototype.events, {
        'focus input': '_onBarcodeFieldFocus',
    }),
    _onBarcodeFieldFocus: function (ev) {
        this.$input.select();
    },
    _exactLocationSearch: function (value) {
        var self = this;
        return this._rpc({
            model: 'stock.location',
            method: 'search_read',
            kwargs: {
                domain: [['barcode', '=', value]],
                fields: ['id', 'display_name'],
                limit: 2,
            },
        }).then(function (results) {
            if (results.length === 1) {
                var rec = results[0];
                self.reinitialize({ id: rec.id, display_name: rec.display_name });
                self._setValue({ id: rec.id, display_name: rec.display_name });
            } else if (results.length === 0) {
                self.do_notify(_.str.sprintf("No location found with barcode '%s'", value));
            }
        });
    },
});


fieldRegistry.add('mrp_lot_barcode_scan', FieldMany2OneBarcodeLot);
fieldRegistry.add('mrp_location_barcode_scan', FieldMany2OneBarcodeLocation);


return {
    FieldMany2OneBarcodeLot: FieldMany2OneBarcodeLot,
    FieldMany2OneBarcodeLocation: FieldMany2OneBarcodeLocation,
};
});