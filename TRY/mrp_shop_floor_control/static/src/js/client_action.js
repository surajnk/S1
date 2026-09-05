odoo.define('mrp_shop_floor_control.ClientAction', function (require) {
'use strict';

const { ComponentWrapper } = require('web.OwlCompatibility');

var concurrency = require('web.concurrency');
var core = require('web.core');
var Pager = require('web.Pager');
var AbstractAction = require('web.AbstractAction');
var Dialog = require('web.Dialog');
var field_utils = require('web.field_utils');

var QWeb = core.qweb;
var _t = core._t;

const defaultPagerSize = 20;


var ClientAction = AbstractAction.extend({
    contentTemplate: 'wc_capacity_report',
    hasControlPanel: true,
    loadControlPanel: false,
    withSearchBar: false,
    searchMenuTypes: ['filter', 'favorite'],
    custom_events: _.extend({}, AbstractAction.prototype.custom_events, {
        pager_changed: '_onPagerChanged',
    }),
    events: {
//        'change .o_fps_input_planned_qty': '_onChangeInputPlannedQty',
//        'click .o_po_parent': '_onClickPoParent',
//        'click .o_view_po': '_onClickViewPo',
        'click button.o_wcc_button_prev': '_onClickFpsButtonPrev',
        'click button.o_wcc_button_today': '_onClickFpsButtonToday',
        'click button.o_wcc_button_next': '_onClickFpsButtonNext',
        'click button.o_wcc_button_change_date': '_onClickFpsButtonChangeDate',
    },

    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.actionManager = parent;
        this.action = action;
        this.context = action.context;
        this.order_start_date = false
        this.order_end_date = false
        if (action.context.order_start_date){
            this.order_start_date = action.context.order_start_date;
        }
        if (action.context.order_end_date){
            this.order_end_date = action.context.order_end_date;
        }
        this.Datas = {}
        this.domain = [];

        this.companyId = false;
        this.timePeriod = false;
        this.timePeriods = [];
        this.state = false;

        this.active_ids = [];
        this.pager = false;
        this.recordsPager = false;
        this.Titles = []
        this.mutex = new concurrency.Mutex();

//        this.searchModelConfig.modelName = 'mrp.workcenter.capacity.report';
    },

    async willStart() {
        await this._super(...arguments);
//        const searchQuery = this.controlPanelProps.searchModel.get("query");
//        this.domain = searchQuery.domain;
        await this._getOrderStartDate()
        await this._getTitles()
        await this._getDatas()
    },

    start: async function () {
        await this._super(...arguments);
//        if (this.state.length == 0) {
//            this.$el.find('.o_mrp_mps').append($(QWeb.render('mrp_mps_nocontent_helper')));
//        }
        await this.update_cp();
//        await this.renderPager();
    },

    // ---------------------------------------------------------------------------
    //    Events
    // ---------------------------------------------------------------------------

    _onClickPoParent: function (ev) {
        ev.stopPropagation();
        var $target = $(ev.target);
        if ($target && $target[0].tagName != 'A'){
            this.$el.find('tr[data-line_id=' + $target.closest('tr').data('id') + ']').toggleClass("show_po_line")
        }
    },

    _onClickViewPo: function (ev) {
        var self = this;
        var $target = $(ev.target);
        return self.do_action({
            name: 'Purchase Order',
            type: 'ir.actions.act_window',
            res_model: 'purchase.order',
            views: [[false, 'form']],
            res_id: $target.data('id'),
        });
    },

    _onClickFpsButtonPoImport: function (ev) {
        var self = this;
        return self.do_action({
            name: 'Import Purchase Planning',
            type: 'ir.actions.act_window',
            res_model: 'import.purchase.planning.wiz',
            views: [[false, 'form']],
            target: 'new',
        });
    },

    _onClickFpsButtonPrev: function (ev) {
        var self = this;
        var order_start_date = this.order_start_date
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_order_start_date',
            args: [order_start_date, 'prev']
        }).then(function (order_start_date) {
            self.order_start_date = order_start_date;
            self._reloadContent();
        });
    },

    _onClickFpsButtonToday: function (ev) {
        var self = this;
        var order_start_date = this.order_start_date
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_order_start_date',
            args: [order_start_date, 'today']
        }).then(function (order_start_date) {
            self.order_start_date = order_start_date;
            self._reloadContent();
        });
    },

    _onClickFpsButtonNext: function (ev) {
        var self = this;
        var order_start_date = this.order_start_date
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_order_start_date',
            args: [order_start_date, 'next']
        }).then(function (order_start_date) {
            self.order_start_date = order_start_date;
            self._reloadContent();
        });
    },

    _onClickFpsButtonChangeDate: function (ev) {
        var self = this;
        return self.do_action({
            name: 'Update Week Date',
            type: 'ir.actions.act_window',
            res_model: 'wc.report.change.date.wiz',
            views: [[false, 'form']],
            target: 'new',
        });

    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    _getOrderStartDate: function () {
        var self = this;
        var order_start_date = this.order_start_date
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_order_start_date',
            args: [order_start_date, '']
        }).then(function (order_start_date) {
            self.order_start_date = order_start_date;
        });
    },

    _getTitles: function () {
        var self = this;
        var order_start_date = this.order_start_date
        var order_end_date = this.order_end_date
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_titles',
            args: [order_start_date, order_end_date]
        }).then(function (titles) {
            self.Titles = titles;
        });
    },

    _getDatas: function () {
        var self = this;
        var order_start_date = this.order_start_date
        var order_end_date = this.order_end_date
//        var purchase_order_ids = this.purchase_order_ids
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_datas',
            args: [order_start_date, order_end_date]
        }).then(function (datas) {
            self.Datas = datas;
        });
    },


    update_cp: async function () {
        this.$buttons = $(QWeb.render('wcc_control_panel_buttons', {groups: this.groups}));
        const res = await this.updateControlPanel({
            title: _t('Work Center Capacity'),
            cp_content: {
                $buttons: this.$buttons,
            },
        });
        return res;
    },

    /**
     * reload all the production schedules inside content. Make an rpc to the
     * server in order to get the updated state and render it.
     *
     * @private
     * @return {Promise}
     */
    _reloadContent: function () {
        var self = this;
        this._getTitles()
        return this._getDatas().then(function () {
            var $content = $(QWeb.render('wc_capacity_report', {
                widget: {
                    Titles: self.Titles,
                    Datas: self.Datas,
                }
            }));
            $('.o_wc_capacity_report').replaceWith($content);
        });
    },

    _onPagerChanged: function (ev) {
        let { currentMinimum, limit } = ev.data;
        this.pager.update({ currentMinimum, limit });
        currentMinimum = currentMinimum - 1;
        this.active_ids = this.recordsPager.slice(currentMinimum, currentMinimum + limit).map(i => i.id);
        this._reloadContent();
    },

});

core.action_registry.add('mrp_workcenter_capacity_report', ClientAction);

return ClientAction;

});
