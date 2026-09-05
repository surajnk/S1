odoo.define('disable_onboarding_tours.disable', function (require) {
"use strict";

var tour = require('web_tour.tour');

// Add any other onboarding tour's technical name here to silence it too -
// no new module file, xpath, or script tag needed, just extend this list.
// Find a tour's name by searching its module's static/src/js/tours/*.js
// file for the first argument passed to tour.register(...).
var DISABLED_TOUR_NAMES = [
    'crm_tour',           // CRM: "Ready to boost your sales?"
    'point_of_sale_tour', // POS: "Ready to launch your point of sale?"
    'project_tour',       // Project: "Want a better way to manage your projects?"
    'mass_mailing_tour',
];

if (tour && tour.tours) {
    DISABLED_TOUR_NAMES.forEach(function (name) {
        if (tour.tours[name]) {
            delete tour.tours[name];
        }
    });
}

});
