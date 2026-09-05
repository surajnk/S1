odoo.define('mrp_shop_floor_control.duration_hours_timer', function (require) {
    'use strict';

    var fields = require('web.basic_fields');
    var fieldRegistry = require('web.field_registry');
    var time = require('web.time');

    var DurationHoursTimer = fields.FieldFloatTime.extend({
        init: function () {
            this._super.apply(this, arguments);
            this.duration_hours = this.record.data.duration_hours || 0;
            this.live_session_seconds = 0;  // will add on top
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
                fields: ['date_start'],
                limit: 1,
            }).then(function (result) {
                if (result.length > 0) {
                    var currentDate = new Date();
                    var startDate = time.auto_str_to_date(result[0].date_start);
                    var seconds = moment(currentDate).diff(moment(startDate), 'seconds');

                    self.live_session_seconds = seconds;
                    self._anyUserWorking = true;
                }
                if (self.mode === 'edit') {
                    self.value = self.duration_hours + (self.live_session_seconds / 3600.0);
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

            this.timer = setTimeout(function () {
                self.live_session_seconds += 1;

                var totalHours = self.duration_hours + (self.live_session_seconds / 3600.0);

                function formatHHMM(hoursFloat) {
                    var totalMinutes = Math.floor(hoursFloat * 60);
                    var hrs = Math.floor(totalMinutes / 60);
                    var mins = totalMinutes % 60;
                    return hrs.toString().padStart(2, '0') + ':' + mins.toString().padStart(2, '0');
                }

                self.$el.text(formatHHMM(totalHours));

                self._startTimeCounter(); // continue ticking
            }, 1000);
        }
    });

    fieldRegistry.add('mrp_time_counter_hours', DurationHoursTimer);
});
