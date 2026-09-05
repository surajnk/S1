
odoo.define('freeze_column_list.FreezeColumnsRenderer', function (require) {
    'use strict';

    const ListRenderer = require('web.ListRenderer');

    const FreezeColumnsRenderer = ListRenderer.extend({
        init(parent, state, params) {
            this.freezeColumns = !!params.arch.attrs.freeze_columns;
            this._super(parent, state, params);
        },
        _renderHeader() {
            const $thead = this._super.apply(this, arguments);
            if (!this.freezeColumns) {
                return $thead;
            }
            const self = this;
            $thead.find('th').each(function (index) {
                const $btn = $('<span class="freeze-col">\uD83D\uDCCC</span>');
                $btn.on('click', ev => {
                    ev.stopPropagation();
                    self._freezeColumns(index);
                });
                $(this).append($btn);
            });
            return $thead;
        },
        _freezeColumns(index) {
            const $table = this.$el.find('table.o_list_table');
            $table.find('th, td')
                .css({position: '', left: '', top: '', zIndex: '', background: ''})
                .removeClass('o_frozen_cell');
            if (index < 0) {
                return;
            }
            const offsets = [];
            $table.find('tr:first').children().each(function (i) {
                offsets[i] = (offsets[i-1] || 0) + $(this).outerWidth();
            });
            $table.find('tr').each(function () {
                let left = 0;
                $(this).children().each(function (i) {
                    if (i <= index) {
                        const css = {
                            position: 'sticky',
                            left: left + 'px',
                            zIndex: 1,
                            background: '#fff',
                        };
                        if ($(this).is('th')) {
                            css.top = '0px';
                            css.zIndex = 3;
                        }
                        $(this).css(css).addClass('o_frozen_cell');
                        left += $(this).outerWidth();
                    }
                });
            });
        },
    });

    return FreezeColumnsRenderer;
});

odoo.define('freeze_column_list.FreezeColumnsListView', function (require) {
    'use strict';

    const ListView = require('web.ListView');
    const viewRegistry = require('web.view_registry');
    const FreezeColumnsRenderer = require('freeze_column_list.FreezeColumnsRenderer');

    const FreezeColumnsListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Renderer: FreezeColumnsRenderer,
        }),
    });

    viewRegistry.add('freeze_columns_list', FreezeColumnsListView);
    return FreezeColumnsListView;
});
