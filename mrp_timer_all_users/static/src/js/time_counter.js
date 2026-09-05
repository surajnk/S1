odoo.define('mrp_timer_all_users.time_counter', function (require) {
    'use strict';

    var fields = require('web.basic_fields');
    var fieldRegistry = require('web.field_registry');
    var fieldUtils = require('web.field_utils');
    var time = require('web.time');

    var TimeCounterAllUsers = fields.FieldFloatTime.extend({
        init: function () {
            this._super.apply(this, arguments);
            this.duration = this.record.data.duration;
            this._anyUserWorking = false;
        },
        willStart: function () {
            var self = this;
            var def = this._rpc({
                model: 'mrp.workcenter.productivity',
                method: 'search_read',
                domain: [
                    ['workorder_id', '=', this.record.data.id],
                    ['date_end', '=', false],
                ],
            }).then(function (result) {
                var currentDate = new Date();
                var duration = 0;
                if (result.length > 0) {
                    duration += self._getDateDifference(time.auto_str_to_date(result[0].date_start), currentDate);
                }
                var minutes = duration / 60 >> 0;
                var seconds = duration % 60;
                self.duration += minutes + seconds / 60;
                self._anyUserWorking = result.length > 0;
                if (self.mode === 'edit') {
                    self.value = self.duration;
                }
            });
            return Promise.all([this._super.apply(this, arguments), def]);
        },
        destroy: function () {
            this._super.apply(this, arguments);
            clearTimeout(this.timer);
        },
        isSet: function () {
            return true;
        },
        _getDateDifference: function (dateStart, dateEnd) {
            return moment(dateEnd).diff(moment(dateStart), 'seconds');
        },
        _renderReadonly: function () {
            if (this._anyUserWorking) {
                this._startTimeCounter();
            } else {
                this._super.apply(this, arguments);
            }
        },
        _startTimeCounter: function () {
            var self = this;
            clearTimeout(this.timer);
            if (this._anyUserWorking) {
                this.timer = setTimeout(function () {
                    self.duration += 1/60;
                    self._startTimeCounter();
                }, 1000);
            } else {
                clearTimeout(this.timer);
            }
            this.$el.text(fieldUtils.format.float_time(this.duration));
        },
    });

    fieldRegistry.add('mrp_time_counter', TimeCounterAllUsers);
});
