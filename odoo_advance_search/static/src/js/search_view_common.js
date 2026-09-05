odoo.define('odoo_advance_search.utils', function (require) {
    'use strict';

    var ajax = require("web.ajax");
    var core = require('web.core');

    var _t = core._t;
    
    function setAsRecordSelect($select, data=false) {
        var select2Options = {
            allowClear: true,
            multiple: true, //$select.is('[multiple]'),
            minimumInputLength: 1,

            formatResult: function(record, resultElem, searchObj) {
                return $("<div/>", {text: record.name}).addClass('o_sign_add_partner');
            },

            formatSelection: function(record) {
                return $("<div/>", {text: record.name}).html();
            },

            ajax: {
                data: function(term, page) {
                    return { 'term': term, 'page': page };
                },
                transport: function(args) {
                    var odoo_model = this.getAttributes().search_model;
                    var context = this.getAttributes().ctx;
                    if(!context){
                    	context="{}";
                    }
                    var ctx = JSON.parse(context);

                	if (odoo_model === undefined){
                		return []
                	}
                    ajax.rpc('/web/dataset/call_kw/'+odoo_model+'/name_search', {
                        model: odoo_model,
                        method: 'name_search',
                        args: [args.data.term],
                        kwargs: {
                            limit: 500,
                            context:ctx
                        }
                    }).then(args.success); //.fail(args.failure)
                },
                results: function(data) {
                    var last_page = data.length !== 500
                    var new_data = [];
                    _.each(data, function(record) {
                    	new_data.push({'id':record[0],'name':record[1]})
                    	/*partner['name'] = partner['name'] || '';
                        partner['email'] = partner['email'] || '';*/
                    });
                    
                    return {'results': new_data, 'more': !last_page};
                },
                quietMillis: 250,
            },
            
            initSelection : function(element, callback) {
            	if ($(element).data('new_id_vals')){
            		var new_id_vals = $(element).data('new_id_vals');
            		data = []
            		for (var key in new_id_vals) {
            			data.push({ id: key, name: new_id_vals[key],isNew: false });
					}
            		
            		//data = {id : parseInt(element.attr('value')), name: element.attr('title'),isNew: false }
                	callback(data);
                }
                else{
                	callback({});
                }
            	/*if (element.attr('value')){
                	data = {id : parseInt(element.attr('value')), name: element.attr('title'),isNew: false }
                	//element.val('');
                	callback(data);
                }
                else{
                	callback({});
                }*/
            	
            }
        };
        
        $select.select2('destroy');
        $select.addClass('form-control');
        $select.select2(select2Options);
        
//        if (data){
//        	$select.select2('data', data);
//		}
        
        $select.off('change').on('change', function(e) {
            if(e.added) {
            	$(this).data('new_id_vals', $(this).data('new_id_vals') || {});
                $(this).data('new_id_vals')[e.added.id] = e.added.name;
            	$(e.target).attr('title',e.added.name)
        		
            } else if(e.removed) {
            	delete $(this).data('new_id_vals')[e.removed.id];
            	$(e.target).attr('title','')
            }
        });
        // fix an issue select2 has to size a placeholder of an invisible input
        setTimeout(function(){
            if ($select.data('select2')){
            	$select.data('select2').clearSearch();
            }
        	
        });
    }
    
    return {setAsRecordSelect: setAsRecordSelect,}
});
