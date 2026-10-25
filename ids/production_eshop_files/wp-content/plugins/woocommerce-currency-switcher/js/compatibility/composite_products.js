"use strict";
//FOX + WooCommerce Composite Products on a cached site, see classes/compatibility/composite_products.php
//Composite computes option prices and the composite total in JavaScript from data embedded in the page.
//On a page taken from a page cache that data is in the currency the page was cached in, so when the
//visitor uses another currency the form data is replaced with data rendered in the visitor currency.
jQuery(function ($) {

    if (typeof woocs_shop_is_cached === 'undefined' || !woocs_shop_is_cached || typeof $.fn.wc_composite_form !== 'function') {
        return;
    }

    var get = (typeof woocs_array_of_get === 'string') ? JSON.parse(woocs_array_of_get) : woocs_array_of_get;
    if (get && typeof get.currency !== 'undefined') {
        return;//the page is rendered for the currency in the URL, not taken from the cache
    }

    var $composites = $('.composite_form .composite_data');
    if (!$composites.length) {
        return;
    }

    var ids = [];
    $composites.each(function () {
        ids.push($(this).data('container_id'));
    });

    var page_currency = (typeof woocs_late_prices !== 'undefined' && woocs_late_prices.page_currency) ? woocs_late_prices.page_currency : woocs_current_currency['name'];

    $.post(woocs_ajaxurl, {
        action: 'woocs_get_composite_form_data',
        composite_ids: ids,
        current_currency: page_currency,
        //original total format, the server adds the visitor currency code to it when the FOX price format has __CODE__
        i18n_price_format: (typeof wc_composite_params !== 'undefined' && wc_composite_params.woocs_i18n_price_format) ? wc_composite_params.woocs_i18n_price_format : undefined
    }, function (data) {

        if (typeof data === 'string') {
            data = JSON.parse(data);
        }

        //empty answer: the page is already in the visitor currency
        if ($.isEmptyObject(data) || $.isEmptyObject(data.forms)) {
            return;
        }

        if (typeof wc_composite_params !== 'undefined' && data.params) {
            $.extend(wc_composite_params, data.params);
        }

        //parsed in a separate document: no scripts run and no images load
        var doc = document.implementation.createHTMLDocument('');

        $composites.each(function () {
            var $composite_data = $(this);
            var id = $composite_data.data('container_id');
            if (!data.forms[id]) {
                return;
            }

            var $fresh = $('<div></div>', doc).append($.parseHTML(data.forms[id], doc));
            var $fresh_data = $fresh.find('.composite_data').filter(function () {
                return String($(this).data('container_id')) === String(id);
            });
            if (!$fresh_data.length) {
                return;
            }

            var $form = $composite_data.closest('.composite_form');
            var $fresh_form = $fresh_data.closest('.composite_form');
            if (!$form.length || !$fresh_form.length) {
                return;
            }

            //keep options the visitor has already chosen while this request was running
            var script = $form.wc_get_composite_script();
            var config = (script && script.api) ? script.api.get_composite_configuration() : false;
            if (config) {
                $fresh_form.find('.composite_component').each(function () {
                    var component_id = String($(this).data('item_id'));
                    var $options = $(this).find('.component_options').first();
                    if (!$options.length || !config[component_id] || typeof config[component_id].product_id === 'undefined') {
                        return;
                    }
                    try {
                        var parsed = JSON.parse($options.attr('data-options_data'));
                        var selected = String(config[component_id].product_id || '');
                        for (var i = 0; i < parsed.length; i++) {
                            parsed[i].is_selected = String(parsed[i].option_id) === selected;
                        }
                        $options.attr('data-options_data', JSON.stringify(parsed));
                    } catch (e) {
                        //keep the fresh data as it is
                    }
                });
            }

            //A fresh, never initialized form, the way Composite itself starts a form loaded later (quick view).
            //Running the initializer again on the form already on the page is not enough: the stepped layouts
            //(progressive, paged) rebuild the form markup on the first start and do not start twice on it.
            var form = document.importNode($fresh_form.get(0), true);
            $form.replaceWith(form);
            //stepped layouts start Backbone's browser history router, it may be started only once
            if (window.Backbone && Backbone.History && Backbone.History.started) {
                Backbone.history.stop();
            }
            $(form).find('.composite_data').wc_composite_form();
            $(document.body).trigger('woocs_composite_form_refreshed', [form]);
        });
    });

});
