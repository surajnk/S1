odoo.define('mrp_shop_floor_control.workorder', function (require) {
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


var workorder = AbstractAction.extend({
    contentTemplate: 'wo_report',
    hasControlPanel: true,
    loadControlPanel: false,
    withSearchBar: false,
    searchMenuTypes: ['filter', 'favorite'],
    custom_events: _.extend({}, AbstractAction.prototype.custom_events, {
        pager_changed: '_onPagerChanged',
    }),
    events: {
        'click button.o_wcc_button_change_date': '_onClickFpsButtonChangeDate',
    },

    init: function (parent, action) {
        this._super.apply(this, arguments);
        this.actionManager = parent;
        this.action = action;
        this.context = action.context;
        this.order_start_date = false
        this.order_end_date = false
        this.manufacturing_order = false
        if (action.context.order_start_date){
            this.order_start_date = action.context.order_start_date;
        }
        if (action.context.order_end_date){
            this.order_end_date = action.context.order_end_date;
        }
        if (action.context.manufacturing_order){
            this.manufacturing_order = action.context.manufacturing_order;
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
    },

    async willStart() {
        await this._super(...arguments);
        await this._getOrderStartDate()
        await this._getTitles()
        await this._getDatas()
    },

    start: async function () {
        await this._super(...arguments);
        await this.update_cp();
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

    _onClickFpsButtonChangeDate: function (ev) {
        var self = this;
        return self.do_action({
            name: 'Work Order Report',
            type: 'ir.actions.act_window',
            res_model: 'wo.report.wiz',
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
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_work_order_titles',
        }).then(function (titles) {
            self.Titles = titles;
        });
    },

    _getDatas: function () {
        var self = this;
        var order_start_date = this.order_start_date
        var order_end_date = this.order_end_date
        var manufacturing_order = this.manufacturing_order
        console.log('strt',order_start_date)
        console.log('end',order_end_date)
        console.log('manu',manufacturing_order)
        return this._rpc({
            model: 'mrp.workcenter.capacity.report',
            method: 'get_workorder_datas',
            args: [order_start_date, order_end_date,manufacturing_order]
        }).then(function (datas) {
            self.Datas = datas;
        });
    },


    update_cp: async function () {
        this.$buttons = $(QWeb.render('wo_control_panel_buttons', {groups: this.groups}));
        const res = await this.updateControlPanel({
            title: _t('Work Order Report'),
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
        console.log('titless',self.Titles)
        console.log('titless',self.Datas)
            var $content = $(QWeb.render('wo_report', {
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

core.action_registry.add('mrp_workorder_report', workorder);

return workorder;

});
