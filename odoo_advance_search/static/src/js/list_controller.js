odoo.define('odoo_advance_search.ListController', function (require) {
"use strict";

var session = require('web.session');
var ListController = require('web.ListController');
var field_utils = require('web.field_utils');

ListController.include({
	events: _.extend({}, ListController.prototype.events, {
    	'change thead .odoo_field_search_expan': '_change_odoo_field_search_expan',
    	'keydown thead .odoo_field_search_expan': '_onkeydownAdvanceSearch',
    }),
	_onSearch: function (searchQuery) {
		this.renderer.original_domain = searchQuery.domain; 
		if (searchQuery.domain != undefined && this.cust_seach_domain != undefined){
			searchQuery.domain = searchQuery.domain.concat(this.cust_seach_domain)
		}
		return this._super(searchQuery);
	},
    _onkeydownAdvanceSearch: function (event) {
    	if (event.keyCode==13){
    		event.preventDefault();
        	event.stopPropagation();
			this.triggerAdvanceSearch();
    	}
    },
    _change_odoo_field_search_expan: function (event) {
    	event.preventDefault();
    	event.stopPropagation();
		this.triggerAdvanceSearch();
		
    },
	triggerAdvanceSearch: function (){
		var renderer = this.renderer;
		self=this;
		var advance_search_val = {'modelName': self.renderer.state.model,
								  'groupBy': self.renderer.state.groupedBy,
								  'context' : self.renderer.state.context,
								  'ids': self.renderer.state.res_ids,
						          'offset' : self.renderer.state.offset, 
								  'currentId': self.renderer.state.res_id,
						          'selectRecords': self.renderer.selection,
								}
		self.cust_seach_domain = [];
    	if (!renderer.def_column_val || renderer.state.model!==self.modelName){
        	renderer.def_column_val = {};
        }
    	if (renderer.state.model===self.modelName){
    		$('.odoo_field_search_expan').each(function(){
        		if (this.value){
        			var cust_field = this;
        			var field_type = this.getAttribute('field_type');
        			for (var i = 0; i < renderer.columns.length; i++ ){
        				if (field_type!==undefined && session.has_advance_search_group && (field_type==='date' || field_type==='datetime')){
        					var field_name_from = renderer.columns[i].attrs.name+'_from';
        					var field_name_to = renderer.columns[i].attrs.name+'_to';
        					if (field_name_from===cust_field.name || field_name_to===cust_field.name){
        						var dt_value = field_utils.parse.date(cust_field.value);
        						renderer.def_column_val[cust_field.name] = dt_value.locale('en').format('YYYY-MM-DD');
            				}
        				}
						else if (field_type!==undefined && !session.has_advance_search_group && (field_type==='date' || field_type==='datetime')){
        					if (renderer.columns[i].attrs.name===cust_field.name){
        						var dt_value = field_utils.parse.date(cust_field.value);
	        					renderer.def_column_val[cust_field.name] = dt_value.locale('en').format('YYYY-MM-DD');
        					}
        				}
						else if (field_type!==undefined && (field_type==='integer' || field_type==='float' || field_type==='monetary')){
        					var field_name_from = renderer.columns[i].attrs.name+'_from';
        					var field_name_to = renderer.columns[i].attrs.name+'_to';
        					if (field_name_from===cust_field.name || field_name_to===cust_field.name){
        						renderer.def_column_val[cust_field.name] = cust_field.value;
            				}
        				}
        				else if (field_type!==undefined && field_type==='many2one'){
        					if (renderer.columns[i].attrs.name===cust_field.name){
        						//renderer.def_column_val[cust_field.name] = [cust_field.value, cust_field.title];
        						renderer.def_column_val[cust_field.name] = $(this).data('new_id_vals') || {};
        					}
        				}
        				else{
        					if (renderer.columns[i].attrs.name===cust_field.name){
            					renderer.def_column_val[cust_field.name] = cust_field.value;
            				}
        				}
        			}
        			if (field_type!==undefined && field_type==='selection'){
        				self.cust_seach_domain.push([this.name,'=',this.value]);
        			}
        			else if (field_type!==undefined && field_type==='boolean'){
        				if (this.value==='true'){
        					self.cust_seach_domain.push([this.name,'=',true]);
        				}
        				else{
        					self.cust_seach_domain.push([this.name,'=',false]);
        				}
        			}
        			else if (field_type!==undefined && (field_type==='date' || field_type==='datetime')){
        				var value = renderer.def_column_val[this.name];
        				if (field_type==='datetime'){
        					var time_vals =  (session.has_advance_search_group && this.name.endsWith('_to')) ? ' 23:59:59' : ' 00:00:00';
        					var d = new Date(value+time_vals);
	                    	var date_value = d.getUTCFullYear()+'-'+(d.getUTCMonth()+1)+'-'+d.getUTCDate()+' '+d.getUTCHours()+':'+d.getUTCMinutes()+':'+d.getUTCSeconds();
        				}
        				else{
        					var date_value = value;
        				}
                    	
        				if (session.has_advance_search_group){
        					if (this.name.endsWith('_from')){
            					var field_name = this.name.substring(0,this.name.lastIndexOf('_from'));
            					self.cust_seach_domain.push([field_name,'>=',date_value]);
            				}
            				else if (this.name.endsWith('_to')){
            					var field_name = this.name.substring(0,this.name.lastIndexOf('_to'));
            					self.cust_seach_domain.push([field_name,'<=',date_value]);
            				}
        				}
        				else{
        					self.cust_seach_domain.push([this.name,'>=',date_value]);
            				var d = new Date(value+' 23:59:59');
        					if (field_type==='datetime'){
        						var date_value_to = d.getUTCFullYear()+'-'+(d.getUTCMonth()+1)+'-'+d.getUTCDate()+' '+d.getUTCHours()+':'+d.getUTCMinutes()+':'+d.getUTCSeconds();
        						self.cust_seach_domain.push([this.name,'<=',date_value_to]);
        					}
        					else{
        						self.cust_seach_domain.push([this.name,'<=',date_value]);
        					}
        				}
        			}
        			else if (field_type!==undefined && (field_type==='integer' || field_type==='float' || field_type==='monetary')){
        				//var value = this.value;
						var value = renderer.def_column_val[this.name];
						
        				if (field_type==='integer'){
        					value = parseInt(this.value);
        				}else{
        					value = parseFloat(this.value);
        				}
						
						if (this.name.endsWith('_from')){
        					var field_name = this.name.substring(0,this.name.lastIndexOf('_from'));
        					self.cust_seach_domain.push([field_name,'=',value]);
        				}
        				else if (this.name.endsWith('_to')){
        					var field_name = this.name.substring(0,this.name.lastIndexOf('_to'));
        					self.cust_seach_domain.push([field_name,'<=',value]);
        				}
        				//self.cust_seach_domain.push([this.name,'=',value]);
        			}
        			else if (field_type!==undefined && (field_type==='many2one')){
        				/*value = parseInt(this.value);
        				self.cust_seach_domain.push([this.name,'=',value]);*/
        				var values = $(this).data('new_id_vals') || {};
        				        values = Object.keys(values).map(Number)
        					if (values.length){
        					    self.cust_seach_domain.push([this.name,'in',values]);
        					}
        			}
        			else{
        				self.cust_seach_domain.push([this.name,'ilike',this.value]);
        			}
        		}
        		else{
        			renderer.def_column_val[this.name] = '';
        		}
        	});
    		
    	}
		if (!renderer.original_domain){
			renderer.original_domain = renderer.state.domain;	
		}
    	if (self.cust_seach_domain !== undefined && self.cust_seach_domain.length>0){
			var domain = renderer.original_domain.concat(self.cust_seach_domain)
			advance_search_val['domain'] = domain;
			
			if (renderer.noContentHelp !== undefined){
    			renderer.noContentHelp=false;
    		}
			self.update(advance_search_val, undefined);
    	}
		else{
			advance_search_val['domain'] = renderer.original_domain;
			self.update(advance_search_val, undefined);
		}
	},
});

});
