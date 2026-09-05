odoo.define('ks_sticky_pivot.stick_header', function (require) {
'use strict';
    var OwlAbstractRenderer = require('web.AbstractRendererOwl');
    var PivotView = require('web.PivotView');
    var PivotRenderer = require('web.PivotRenderer');
    var ks_PivotController = require('web.PivotController');
    var ks_Session = require('web.session');
    var core = require('web.core');
    var QWeb = core.qweb;
    const PivotController = require("web.PivotController");
    var ajax = require('web.ajax');
    const patchMixin = require('web.patchMixin');
    const { useListener } = require('web.custom_hooks');

    const { useExternalListener, useState, onMounted, onPatched } = owl.hooks;

    PivotRenderer.patch("sticky_pivot", ks_sticky_head => class extends ks_sticky_head {
        constructor(){

          super(...arguments);
//          useListener('.dropdown-item', 'click', '_KsCellValue');
          if(ks_Session.ks_pivot_status_header){
            ajax.loadCSS("/ks_sticky_pivot_view/static/src/css/ks_stick.css")
          }
        onMounted(() => this.ksUpdateTooltip());
        onPatched(() => this.ksUpdateTooltip());

        }

        ksUpdateTooltip() {
            if ($('.o_pivot_field_menu').hasClass('show') && $('.o_pivot_field_menu').offset().top >400){
                    $('.o_pivot_field_menu').addClass('ks_dropdown_bottom')
                     $('.ks_sticky_header_custom').addClass('ks_remove_sticky_header')
                $('.ks_sticky_header_custom th.o_pivot_header_cell_closed').addClass('ks_remove_sticky_header_th')
            }else {
                $('.ks_sticky_header_custom').removeClass('ks_remove_sticky_header')
                $('.ks_sticky_header_custom th.o_pivot_header_cell_closed').removeClass('ks_remove_sticky_header_th')
            }
        }


    });

});

