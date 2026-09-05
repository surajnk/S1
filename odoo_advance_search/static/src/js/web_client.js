odoo.define('odoo_advance_search.WebClient', function(require) {
    "use strict";
    var WebClient = require('web.WebClient');
    WebClient.include({
        start: function() {
            odoo.odoo_web_client = this;
            return this._super.apply(this, arguments);
        }
    });
});