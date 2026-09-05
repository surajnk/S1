odoo.define('odoo_advance_search.Listrenderer', function (require) {
"use strict";

var core = require('web.core');
var session = require('web.session');
var ListRenderer = require('web.ListRenderer');
var _t = core._t;
var pyUtils = require('web.py_utils');
var datepicker = require('web.datepicker');

var odoo_advance_search_utils = require('odoo_advance_search.utils');

ListRenderer.include({
	_onKeyPress: function(){
		return
	},
	setRowMode: function (recordID, mode) {
        var self = this;
        var res = this._super(recordID, mode)
        if (this.getParent().hasActionMenus){
        	var record = self._getRecord(recordID);
            if (record) {
            	var editMode = (mode === 'edit');
            	var $row = this._getRow(recordID);
            	this.currentRow = editMode ? $row.prop('rowIndex') - 2 : null;
            }
        }
        return res;
    },
    _renderBody: function () {
    	var $body = this._super.apply(this, arguments);
    	if (this.getParent().hasActionMenus && this.hasHandle && this.currentRow !== null && this.isEditable()) {
    		this.currentRow = this.currentRow - 1;
    	}
    	return $body;
    },
    _selectCell: function (rowIndex, fieldIndex, options) {
        if (this.getParent().hasActionMenus && this.isEditable() && rowIndex>0){
        	rowIndex = rowIndex-1
        }
        return this._super(rowIndex, fieldIndex, options);
    },
	_renderHeader: function (isGrouped) {
		var $thead = this._super(isGrouped);
		var self = this;
        if(self.def_column_val===undefined){
        	self.def_column_val = {}
        }
		var initial_view = '';
        if(!this.getParent().hasActionMenus && this.getParent().getParent()){
        	if(this.getParent().getParent().options){
        		initial_view = this.getParent().getParent().options.initial_view;
        	}
        }        
        if (this.getParent().hasActionMenus || initial_view==='search'){
        	var context = {}
        	if (self.getParent().initialState !== undefined ){
        		context = pyUtils.eval('contexts', [self.getParent().initialState.getContext()]);
        	}
        	else if (initial_view==='search'){
        		context = pyUtils.eval('contexts', [this.getParent().getParent().searchview.dataset.get_context()]);
        	}
        	var $tr2 = $("<tr class='advance_search_row'>").append(_.map(this.columns,function (column) {
            	var $td = $('<td>');
            	var field_name = column.attrs.name;
            	var field = self.state.fields[field_name];
            	if (!field || !field.searchable || (column.attrs.widget!==undefined && column.attrs.widget==='handle') || (column.attrs.widget!==undefined && column.attrs.widget==='activity_exception')){
            		return $td;
            	}
            	var field_value = self.def_column_val[field_name]
        		if(!field_value){field_value =''}
            	
            	if (field.type === 'integer' || field.type === 'float' || field.type === 'monetary'){
            		//var input_tag = "<input type='number' class='odoo_field_search_expan o_list_number' name='"+field_name+"' field_type='"+field.type+"' style='width:100%;'"+" value='"+field_value+"'>";
            		//var $input = $(input_tag);

					var field_value_from = self.def_column_val[field_name+'_from']
            		var field_value_to = self.def_column_val[field_name+'_to']
            		if(!field_value_from){field_value_from =''}
            		if(!field_value_to){field_value_to =''}
					
					var $wrapper = $("<div>", {});
					var $input_tag = $("<input type='number' class='odoo_field_search_expan o_list_number' name='"+field_name+"_from' field_type='"+field.type+"' style='width:100%;text-align:right;'"+" value='"+field_value_from+"'>");
            		$wrapper.append($input_tag);
					
					var $input_tag = $("<input type='hidden' class='odoo_field_search_expan o_list_number' name='"+field_name+"_to' field_type='"+field.type+"' style='width:100%;text-align:right;'"+" value='"+field_value_to+"'>");
            		$wrapper.append($input_tag);
					
					var $input = $wrapper;
            	}
            	else if (field.type === 'many2one'){
            		var $input1 = $('<input type="hidden"/>').attr('class', 'odoo_field_search_expan o_list_text');
            		$input1.attr('name',field_name);
            		$input1.attr('field_type',field.type);
            		$input1.attr('style','width:100%;');
            		$input1.attr('search_model',field.relation);
            		$input1.attr('placeholder','select');
            		$input1.attr('ctx',JSON.stringify(context));

            		$input1.data('new_id_vals', field_value);
            		$input1.attr('value',field_value);
            		
            		var $input = $('<div/>').append($input1); //.addClass('col-md-9');
            		
            		odoo_advance_search_utils.setAsRecordSelect($input1);
            		
            	}
            	else if (field.type === 'text' || field.type === 'char' || field.type === 'one2many' || field.type === 'many2many' || field.type === 'many2one'){
            		var input_tag = "<input type='text' class='odoo_field_search_expan o_list_text' name='"+field_name+"' field_type='"+field.type+"' style='width:100%;'"+" value='"+field_value+"'>";
            		var $input = $(input_tag);
            	}
            	else if (field.type === 'boolean'){
            		var input_tag = "<select class='odoo_field_search_expan' name='"+field_name+"' field_type='"+field.type+"' style='width:100%;'"+">";
            		var $input = $(input_tag);
            		
            		$input[0].add($('<option>')[0])
            		field_value === 'true' ? $input[0].add($("<option selected=true value='true'>").text(_t("Yes"))[0]) : $input[0].add($("<option value='true'>").text(_t("Yes"))[0]) ;
            		field_value ==='false' ? $input[0].add($("<option selected=true value='false'>").text(_t("No"))[0]) : $input[0].add($("<option value='false'>").text(_t("No"))[0]) ; 
                }
            	else if (field.type === 'date' || field.type === 'datetime'){
            		if (session.has_advance_search_group){
            			var field_value_from = self.def_column_val[field_name+'_from']
                		var field_value_to = self.def_column_val[field_name+'_to']
                		if(!field_value_from){field_value_from =''}
                		if(!field_value_to){field_value_to =''}
                		
                		column.date_from_widget = new datepicker.DateWidget(column, {defaultDate:field_value_from});
                		column.date_to_widget = new datepicker.DateWidget(column, {defaultDate:field_value_to});
                		
                		var $wrapper = $("<div>", {});
                		
                		column.date_from_widget.appendTo($wrapper).then(function() {
                			column.date_from_widget.$el.addClass('o_field_date');
                			column.date_from_widget.$input.attr('placeholder', _t("From :")).addClass('odoo_field_search_expan');
                			column.date_from_widget.$input.attr('name', field_name+'_from');
                			column.date_from_widget.$input.attr('field_type', field.type);
                			column.date_from_widget.on('datetime_changed', self, self.onchangeDatetimeSearch.bind(self, column));
                        });
                		
            			column.date_to_widget.appendTo($wrapper).then(function() {
	            			column.date_to_widget.$el.addClass('o_field_date');
	            			column.date_to_widget.$input.attr('placeholder', _t("To :")).addClass('odoo_field_search_expan');
	            			column.date_to_widget.$input.attr('name', field_name+'_to');
	            			column.date_to_widget.$input.attr('field_type', field.type);
	            			column.date_to_widget.$input.attr('tabindex', -1);
	            			column.date_to_widget.on('datetime_changed', self, self.onchangeDatetimeSearchTo.bind(self, column));
            			});
            		}
            		else{
            			column.date_widget = new datepicker.DateWidget(column, {defaultDate:field_value || null});
            			
            			var $wrapper = $("<div>", {});
            			column.date_widget.appendTo($wrapper).then(function() {
	            			column.date_widget.$el.addClass('o_field_date');
	            			column.date_widget.$input.attr('placeholder', _t("Date :")).addClass('odoo_field_search_expan');
	            			column.date_widget.$input.attr('name', field_name);
	            			column.date_widget.$input.attr('field_type', field.type);
	            			column.date_widget.on('datetime_changed', self, self.onchangeDatetimeSearchToFrom.bind(self, column));
            			});
            		} 
            		
            		var $input = $wrapper;
            		
            		/*if (session.has_advance_search_group){
            			var field_value_from = self.def_column_val[field_name+'_from']
                		var field_value_to = self.def_column_val[field_name+'_to']
                		if(!field_value_from){field_value_from =''}
                		if(!field_value_to){field_value_to =''}
                		
                		var input_tag1 = "<div><input type='date' class='odoo_field_search_expan' name='"+field_name+"_from' field_type='"+field.type+"' placeholder='From :' style='float:left;width:100%;line-height: inherit;' value='"+field_value_from+"'></div>";
                		var input_tag2 = "<div><input type='date' class='odoo_field_search_expan' name='"+field_name+"_to' field_type='"+field.type+"' placeholder='To :' style='float:left;width:100%;line-height: inherit;margin-top:5px;' value='"+field_value_to+"'></div>";
                		var input_tag = input_tag1 + input_tag2;
            		}
            		else{
            			var input_tag = "<input type='date' class='odoo_field_search_expan' name='"+field_name+"' field_type='"+field.type+"' style='float:left;width:100%;line-height: inherit;' value='"+field_value+"'>";
            		} 
            		
            		var $input = $(input_tag);*/
            	}
            	else if (field.type === 'selection'){
            		var input_tag = "<select class='odoo_field_search_expan' name='"+field_name+"' field_type='"+field.type+"' style='width:100%;'>"
            		var $input = $(input_tag);
            		$input[0].add($('<option>')[0]);
            		$.each(field.selection,function(index){
            			var key = field.selection[index][0];
            			var value = field.selection[index][1];
            			var selected = self.def_column_val[field_name] === key
            			if(selected){
            				var option_tag = "<option selected='selected' value='"+key+"'>";
            				$input[0].add($(option_tag).text(value)[0]);
            			}
            			else{
            				var option_tag = "<option value='"+ key +"' >";
            				$input[0].add($(option_tag).text(value)[0]);
            			}
            		})
            	}
            	$td.append($input)
            	return $td;
            }));
        	if (this.hasSelectors) {
                $tr2.prepend($('<td>'));
            }
            
            if ($thead.find("th.o_list_row_number_header").length>0){
            	$tr2.prepend($('<td class="o_list_row_number_header">').html('&nbsp;'));
            }
            
            $thead.append($tr2);
        }
        return $thead;
	},
	onchangeDatetimeSearch: function(column) {
		if (column.date_from_widget.getValue()===undefined){
			return
		}
		try{
			this.getParent().getParent().controllers[this.getParent().controllerID].widget.triggerAdvanceSearch();
		}catch (e) {
            console.error("No controlpanel found");
        }
	},
	onchangeDatetimeSearchTo: function(column) {
		if (column.date_to_widget.getValue()===undefined){
			return
		}
		try{
			this.getParent().getParent().controllers[this.getParent().controllerID].widget.triggerAdvanceSearch();
		}catch (e) {
            console.error("No controlpanel found");
        }
	},
	onchangeDatetimeSearchToFrom: function(column) {
		if (column.date_widget.getValue()===undefined){
			return
		}
		try{
			this.getParent().getParent().controllers[this.getParent().controllerID].widget.triggerAdvanceSearch();
		}catch (e) {
            console.error("No controlpanel found");
        }
	},
});

});
