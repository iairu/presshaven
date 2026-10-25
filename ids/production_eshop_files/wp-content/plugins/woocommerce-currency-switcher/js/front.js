"use strict";
var woocs_loading_first_time = true;//simply flag var
var woocs_sumbit_currency_changing = true;//just a flag variable for drop-down redraws when prices redraws by AJAX


// Unique per-browser storage key. Generated once and kept in localStorage forever.
// Used ONLY in browser key mode as the storage key instead of the visitor IP.
// IMPORTANT: the value must stay lowercase. The PHP side runs it through
// sanitize_key(), which lowercases, so an uppercase character here would produce
// a different md5 on the server and silently split the storage bucket in two.
var woocs_sk = '';
if (typeof woocs_browser_key_mode !== 'undefined' && woocs_browser_key_mode) {
    try {
        woocs_sk = localStorage.getItem('woocs_sk') || '';
        if (!woocs_sk) {
            woocs_sk = (window.crypto && crypto.randomUUID)
                    ? crypto.randomUUID().replace(/-/g, '')
                    : String(Date.now()) + Math.random().toString(36).slice(2, 12);
            localStorage.setItem('woocs_sk', woocs_sk);
        }
    } catch (e) {
        woocs_sk = ''; // private mode / storage disabled: silently fall back to the IP based key
    }
}

// Must run at top level, NOT on document ready: WooCommerce Blocks and the Store API
// start calling fetch() before ready fires, and anything sent earlier misses the key.
// jQuery covers admin-ajax and wc-ajax (see ajaxSend below); fetch() based callers -
// Blocks, the Store API, PayPal PPCP - never pass through jQuery, so the key has to
// travel as a request header. A header, not a query argument: a per visitor query
// argument would fragment the page cache per visitor.
if (woocs_sk && window.fetch) {
    var woocs_native_fetch = window.fetch;
    window.fetch = function (input, init) {

        var url = (typeof input === 'string') ? input : (input && input.url) || '';

        // Same origin only. A custom header on a cross origin request triggers a
        // preflight and can break payment SDKs loaded from third party domains.
        if (url.indexOf('http') === 0 && url.indexOf(window.location.origin) !== 0) {
            return woocs_native_fetch(input, init);
        }

        init = init || {};
        init.headers = new Headers(init.headers || (input && input.headers) || {});
        if (!init.headers.has('X-WOOCS-SK')) {
            init.headers.set('X-WOOCS-SK', woocs_sk);
        }
        return woocs_native_fetch(input, init);
    };
}

jQuery(function ($) {

    if (typeof woocs_array_of_get === 'undefined') {
        return;//to avoid notices and errors
    }

    woocs_array_of_get = JSON.parse(woocs_array_of_get);

    // Attach the browser key to every AJAX request (admin-ajax and wc-ajax),
    // so the cart and the checkout resolve the same currency as the catalog pages.
    if (woocs_sk) {
        $(document).ajaxSend(function (e, xhr, settings) {
            if (typeof settings.data === 'string' && settings.data.indexOf('woocs_sk=') === -1) {
                settings.data += (settings.data ? '&' : '') + 'woocs_sk=' + encodeURIComponent(woocs_sk);
            }
        });


        // A currency arrived in the URL, but a plain page load carries no browser key,
        // so the value was stored under the IP key. Mirror it to the browser key bucket
        // before any redraw runs, otherwise the redraw reads an empty bucket and falls
        // back to the base currency.
        // Uppercased on purpose: the URL handler uses strtoupper() while set_currency()
        // stores whatever it is given, so a lowercase code would be saved as is and then
        // never match the currency array keys.
        if (woocs_array_of_get.currency !== undefined) {
            jQuery.post(woocs_ajaxurl, {
                action: 'woocs_set_currency_ajax',
                currency: String(woocs_array_of_get.currency).toUpperCase()
            }, function () {
                // The mini cart HTML is cached in sessionStorage keyed by the CART hash,
                // and the currency is not part of that hash - so the stale fragment would
                // otherwise survive every later navigation. Refresh it now that the
                // storage bucket already holds the new currency.
                jQuery(document.body).trigger('wc_fragment_refresh');
            });
        }
    }

    //wp-content\plugins\woocommerce\assets\js\frontend\cart.js
    if (Object.keys(woocs_array_of_get).length !== 0) {
        if ('currency' in woocs_array_of_get) {
            //this code nessesary for correct redrawing of the shipping methods while currency changes on the cart page
            $('body.woocommerce-cart .shop_table.cart').closest('form').find('input[name="update_cart"]').prop('disabled', false);
            $('body.woocommerce-cart .shop_table.cart').closest('form').find('input[name="update_cart"]').trigger('click');
        }
    }

    //keeps data of $_GET array

    if (Object.keys(woocs_array_of_get).length == 0) {
        woocs_array_of_get = {};
    }

    //***
    woocs_array_no_cents = JSON.parse(woocs_array_no_cents);

    //***

    //emptying cart widget after checkout
    if (!parseInt(woocs_get_cookie('woocommerce_items_in_cart'), 10)) {
        $('.widget_shopping_cart_content').empty();
        $(document.body).trigger('wc_fragment_refresh');
    }

    if (woocs_array_of_get.currency != undefined || woocs_array_of_get.removed_item != undefined || woocs_array_of_get.key != undefined)
    {
        woocs_refresh_mini_cart(555);
    }
    if (woocs_redraw_cart) {
        //intercept adding to cart event to redraw mini-cart widget
        jQuery(document).on("adding_to_cart", function () {
            woocs_refresh_mini_cart(999);
        });
    }

    //to make price popup mobile friendly
    jQuery('body').on('click', '.woocs_price_info', function () {
        return false;
    });

    //+++++++++++++++++++++++++++++++++++++++++++++++

    if (woocs_drop_down_view == 'chosen' || woocs_drop_down_view == 'chosen_dark') {
        try {
            if (jQuery("select.woocommerce-currency-switcher").not('.woocs_clean_select').length) {
                jQuery("select.woocommerce-currency-switcher").not('.woocs_clean_select').chosen({
                    disable_search_threshold: 10
                });

                jQuery.each(jQuery('.woocommerce-currency-switcher-form .chosen-container'), function (index, obj) {
                    jQuery(obj).css({'width': jQuery(this).prev('select').data('width')});
                });
            }
        } catch (e) {
            console.log(e);
        }
    }



    if (woocs_drop_down_view == 'ddslick') {
        try {
            woocs_init_ddslick_select();

        } catch (e) {
            console.log(e);
        }
    }

    woocs_loading_first_time = false;


    if (woocs_drop_down_view == 'wselect' && woocs_is_mobile != 1) {
        try {
            //https://github.com/websanova/wSelect#wselectjs
            jQuery('select.woocommerce-currency-switcher').not('.woocs_clean_select').wSelect({
                size: 7
            });
        } catch (e) {
            console.log(e);
        }
    }

    //for flags view instead of drop-down
    jQuery('.woocs_flag_view_item').on("click", function () {
        if (woocs_sumbit_currency_changing) {
            if (jQuery(this).hasClass('woocs_flag_view_item_current')) {
                return false;
            }
            //***

            if (Object.keys(woocs_array_of_get).length == 0) {
                window.location = window.location.href + '?currency=' + jQuery(this).data('currency');
            } else {

                woocs_redirect(jQuery(this).data('currency'));

            }
        }

        return false;
    });

    //for converter
    if (jQuery('.woocs_converter_shortcode').length) {
        jQuery('.woocs_converter_shortcode_button').on("click", function () {
            var amount = jQuery(this).parent('.woocs_converter_shortcode').find('.woocs_converter_shortcode_amount').eq(0).val();
            var from = jQuery(this).parent('.woocs_converter_shortcode').find('.woocs_converter_shortcode_from').eq(0).val();
            var to = jQuery(this).parent('.woocs_converter_shortcode').find('.woocs_converter_shortcode_to').eq(0).val();
            var precision = jQuery(this).parent('.woocs_converter_shortcode').find('.woocs_converter_shortcode_precision').eq(0).val();
            var results_obj = jQuery(this).parent('.woocs_converter_shortcode').find('.woocs_converter_shortcode_results').eq(0);
            jQuery(results_obj).val(woocs_lang_loading + ' ...');
            var data = {
                action: "woocs_convert_currency",
                amount: amount,
                from: from,
                to: to,
                precision: precision
            };

            jQuery.post(woocs_ajaxurl, data, function (value) {
                jQuery(results_obj).val(value);
            });

            return false;

        });
    }

    //for rates
    if (jQuery('.woocs_rates_shortcode').length) {
        jQuery('body').on('change', '.woocs_rates_current_currency', function () {
            var _this = this;
            var data = {
                action: "woocs_rates_current_currency",
                current_currency: jQuery(this).val(),
                precision: jQuery(this).data('precision'),
                exclude: jQuery(this).data('exclude')
            };

            jQuery.post(woocs_ajaxurl, data, function (html) {
                jQuery(_this).parent('.woocs_rates_shortcode').html(html);
            });

            return false;

        });
    }

    //if we using js price update while the site is cached
    if (typeof woocs_shop_is_cached !== 'undefined') {
        if (woocs_shop_is_cached) {

            woocs_late_prices_watch();

            setTimeout(function () {

                woocs_sumbit_currency_changing = false;
                if (typeof woocs_array_of_get.currency === 'undefined') {

                    if (jQuery('body').hasClass('single')) {
                        // jQuery('.woocs_price_info').remove();
                    }

                    /****/
                    var custom_prices = [];
                    jQuery.each(jQuery('.woocs_amount_custom_price'), function (index, item) {
                        let decimals = jQuery(item).data('decimals');
                        let value = jQuery(item).data('value');
                        let currency = jQuery(item).data('currency');
                        custom_prices.push({
                            decimals: decimals,
                            value: value,
                            currency: currency
                        });
                    });
                    if (custom_prices.length != 0) {

                        var data = {
                            action: "woocs_get_custom_price_html",
                            custom_prices: custom_prices,
                            current_currency: woocs_current_currency['name']
                        };
                        jQuery.post(woocs_ajaxurl, data, function (data) {
                            // The server answers with wp_send_json (already parsed by jQuery)
                            // in one branch and with wp_die(json_encode()) (plain string) in another.
                            if (typeof data === 'string') {
                                data = JSON.parse(data);
                            }
                            if (!jQuery.isEmptyObject(data)) {
                                jQuery.each(data, function (val, price) {
                                    jQuery(".woocs_amount_custom_price[data-value='" + val + "']").replaceWith(price);
                                });

                            }
                        });
                    }


                    /****/

                    var variation_ids = [];
                    var var_data = jQuery("form.variations_form").data("product_variations");
                    if (typeof var_data != "undefined") {
                        jQuery.each(var_data, function (indx, attr) {
                            variation_ids.push(attr['variation_id']);
                        });
                        if (variation_ids.length != 0) {
                            var data_var = {
                                action: "woocs_get_variation_products_price_html",
                                var_products_ids: variation_ids,
                                current_currency: woocs_current_currency['name']
                            };

                            jQuery.post(woocs_ajaxurl, data_var, function (data) {
                                // The server answers with wp_send_json (already parsed by jQuery)
                                // in one branch and with wp_die(json_encode()) (plain string) in another.
                                if (typeof data === 'string') {
                                    data = JSON.parse(data);
                                }

                                if (!jQuery.isEmptyObject(data)) {
                                    jQuery.each(var_data, function (indx, attr) {
                                        if (typeof data[attr['variation_id']] != "undefined") {
                                            var_data[indx]['price_html'] = data[attr['variation_id']];
                                        }
                                    });
                                    jQuery("form.variations_form").data("product_variations", var_data);
                                }
                            });
                        }
                    }

                    //***
                    var products_ids = {};
                    var products_currency = {};
                    jQuery.each(jQuery('.woocs_price_code'), function (index, item) {
                        products_ids[jQuery(item).data('redraw-id')] = jQuery(item).data('product-id');
                        if (jQuery(item).data('currency')) {
                            products_currency[jQuery(item).data('redraw-id')] = jQuery(item).data('currency');
                        }

                    });

                    //if no prices on the page - do nothing
                    if (Object.keys(products_ids).length === 0) {
                        woocs_sumbit_currency_changing = true;
                        woocs_late_prices_ready('');
                        return;
                    }

                    var data = {
                        action: "woocs_get_products_price_html",
                        products_ids: products_ids,
                        products_currency: products_currency,
                        current_currency: woocs_current_currency['name']
                    };

                    jQuery.post(woocs_ajaxurl, data, function (data) {

                        // The server answers with wp_send_json (already parsed by jQuery)
                        // in one branch and with wp_die(json_encode()) (plain string) in another.
                        if (typeof data === 'string') {
                            data = JSON.parse(data);
                        }

                        if (jQuery.isEmptyObject(data)) {
                            woocs_sumbit_currency_changing = true;
                            //the server answers empty when the page was rendered in the visitor currency
                            woocs_late_prices_ready(woocs_late_prices.page_currency);
                        }
                        if (!jQuery.isEmptyObject(data)) {
                            jQuery('.woocs_price_info').remove();
                            jQuery('.woocs_price_approx.woocs_cart_item_price').remove();
                            jQuery.each(jQuery('.woocs_price_code'), function (index, item) {
                                if (data.ids[jQuery(item).data('redraw-id')] != undefined) {
                                    jQuery(item).replaceWith(data.ids[jQuery(item).data('redraw-id')]);
                                }


                            });
                            jQuery('.woocs_price_code').removeClass('woocs_preloader_ajax');
                            //***
                            jQuery('.woocommerce-currency-switcher').val(data.current_currency);
                            //***
                            if (woocs_drop_down_view == 'chosen' || woocs_drop_down_view == 'chosen_dark') {
                                try {
                                    if (jQuery("select.woocommerce-currency-switcher").not('.woocs_clean_select').length) {
                                        jQuery("select.woocommerce-currency-switcher").not('.woocs_clean_select').chosen({
                                            disable_search_threshold: 10
                                        });
                                        jQuery('select.woocommerce-currency-switcher').trigger("chosen:updated");
                                    }
                                } catch (e) {
                                    console.log(e);
                                }
                            }
                            if (typeof data.currency_data != "undefined") {
                                woocs_current_currency = data.currency_data;
                                /* Price  slider */
                                var min = jQuery('.price_slider_amount #min_price').val();
                                var max = jQuery('.price_slider_amount #max_price').val();
                                if (typeof max != 'undefined' && typeof min != 'undefined') {
                                    max = woocs_convert_price_slider(max);
                                    min = woocs_convert_price_slider(min);
                                    jQuery(document.body).trigger('price_slider_create', [min, max]);
                                }
                            }
                            //***
                            if (woocs_drop_down_view == 'ddslick') {
                                try {
                                    jQuery('div.dd-container').ddslick('destroy');
                                    jQuery('select.woocommerce-currency-switcher').not('.woocs_clean_select').val(data.current_currency);
                                    woocs_init_ddslick_select();
                                } catch (e) {
                                    console.log(e);
                                }
                            }
                            //***
                            if (woocs_drop_down_view == 'wselect' && woocs_is_mobile != 1) {
                                //https://github.com/websanova/wSelect
                                try {
                                    jQuery('select.woocommerce-currency-switcher').not('.woocs_clean_select').val(data.current_currency).trigger("change");
                                } catch (e) {
                                    console.log(e);
                                }
                            }
                            //***
                            /* auto switcher*/

                            var auto_switcher = jQuery('.woocs_auto_switcher');
                            if (auto_switcher.length > 0) {
                                woocs_auto_switcher_redraw(data.current_currency, auto_switcher);
                            }
                            woocs_sumbit_currency_changing = true;

                            var shortcode_currency = jQuery('strong.woocs_current_currency_code');
                            if (shortcode_currency.length) {
                                shortcode_currency.text(data.current_currency);
                            }


                            //***
                            //for another woocs switchers styles
                            document.dispatchEvent(new CustomEvent('after_woocs_get_products_price_html', {detail: {
                                    current_currency: data.current_currency
                                }}));

                            woocs_late_prices_ready(data.current_currency);
                        }

                    }).fail(function () {
                        woocs_late_prices_ready('');
                    });

                } else {
                    woocs_sumbit_currency_changing = true;
                    //the currency came in the URL: such a page is rendered for it, not taken from the cache
                    woocs_late_prices_ready(woocs_late_prices.page_currency);
                }
                jQuery(".single_variation_wrap").on("show_variation", function (event, variation) {
                    jQuery('.woocs_price_code').removeClass('woocs_preloader_ajax');
                });
                jQuery('.woocs_price_code').removeClass('woocs_preloader_ajax');
            }, 300);

        }
    }

    //***
    //removing price info on single page near variation prices
    setTimeout(function () {
        //jQuery('body.single-product .woocommerce-variation-price').find('.woocs_price_info').remove();
    }, 300);
    //***

    //fix: https://pluginus.net/support/topic/wrong-currency-displayed/#postid-100678
    //for shortcode [woocs_show_custom_price value="100"] when sites has cache enabled
    setTimeout(function () {
        // Check if cache mode is enabled
        if (typeof woocs_shop_is_cached !== 'undefined' && woocs_shop_is_cached) {

            // Recalculate custom prices function
            function woocs_recalculate_custom_prices() {
                jQuery('.woocs_amount_custom_price').each(function () {
                    var $item = jQuery(this);
                    var base_value = parseFloat($item.data('value'));
                    var decimals = parseInt($item.data('decimals'));

                    if (isNaN(base_value)) {
                        return;
                    }

                    // Convert to current currency
                    var converted_value = base_value * woocs_current_currency.rate;

                    // Determine decimals
                    if (decimals === -1 || isNaN(decimals)) {
                        decimals = parseInt(woocs_current_currency.decimals);
                    }

                    // Apply hide_cents setting
                    if (woocs_current_currency.hide_cents == 1) {
                        decimals = 0;
                    }

                    // Format number
                    var price_formatted = converted_value.toFixed(decimals);

                    // Apply separators
                    if (woocs_current_currency.separators === "1") {
                        // European format: 1.234,56
                        price_formatted = price_formatted.replace('.', ',');
                        var parts = price_formatted.split(',');
                        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.');
                        price_formatted = parts.join(',');
                    } else {
                        // American format: 1,234.56
                        var parts = price_formatted.split('.');
                        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                        price_formatted = parts.join('.');
                    }

                    // Build HTML with currency symbol
                    var symbol = woocs_current_currency.symbol;
                    var position = woocs_current_currency.position;
                    var final_html = '';

                    switch (position) {
                        case 'left':
                            final_html = symbol + price_formatted;
                            break;
                        case 'left_space':
                            final_html = symbol + '&nbsp;' + price_formatted;
                            break;
                        case 'right':
                            final_html = price_formatted + symbol;
                            break;
                        case 'right_space':
                            final_html = price_formatted + '&nbsp;' + symbol;
                            break;
                        default:
                            final_html = symbol + price_formatted;
                    }

                    // Update inner span with class woocs_amount
                    $item.find('.woocs_amount').html(final_html);
                });

                console.log('WOOCS custom prices recalculated');
            }

            // Run on page load
            woocs_recalculate_custom_prices();

            // Run on currency change
            jQuery(document).on('woocs_currencies_changed', function () {
                setTimeout(woocs_recalculate_custom_prices, 100);
            });
        }
    }, 500);
});


function woocs_redirect(currency) {
    if (!woocs_sumbit_currency_changing) {
        return;
    }

    //***
    var l = window.location.href;
    //  l = l.replace('#', '');
    var l_tmp = l.split('#');
    l = l_tmp[0];
    var id_key = "";
    if (l_tmp.length > 1) {
        id_key = "#" + l_tmp[1]
    }
    //for #id navigation     l = l.replace(/(#.+$)/gi, '');

    l = l.split('?');
    l = l[0];
    var string_of_get = '?';
    woocs_array_of_get.currency = currency;

    /*
     l = l.replace(/(\?currency=[a-zA-Z]+)/g, '?');
     l = l.replace(/(&currency=[a-zA-Z]+)/g, '');
     */

    if (woocs_special_ajax_mode) {
        string_of_get = "";

        var data = {
            action: "woocs_set_currency_ajax",
            currency: currency
        };

        jQuery.post(woocs_ajaxurl, data, function (value) {
            location.reload();
        });

    } else {

        if (Object.keys(woocs_array_of_get).length > 0) {
            let get_values = [];
            jQuery.each(woocs_array_of_get, function (index, value) {
                get_values.push(index + "=" + value);
            });
            string_of_get += get_values.join("&");
        }

        if (woocs_sk) {
            jQuery.post(woocs_ajaxurl, {
                action: "woocs_set_currency_ajax",
                currency: currency,
                woocs_sk
            }, function (value) {
                window.location = l + string_of_get + id_key;
            });

        } else {
            window.location = l + string_of_get + id_key;
        }

    }
}

//+++
//Cache mode: prices inserted into the page after the first redraw pass (Composite Products options,
//Product Bundles, quick views, AJAX fragments) are not part of that pass. Their markup may come from a
//page cache, so it may carry the preloader class and be in another currency than the visitor uses.
//Watch for them and, as soon as they appear, either just clear the preloader (the markup is already in
//the visitor currency) or redraw them in the visitor currency.
var woocs_late_prices = {
    pending: true, //until the first redraw pass answers
    visitor_currency: '', //'' while unknown
    page_currency: '', //the currency the page markup was rendered in
    queue: [],
    html: {}, //redraw-id => price html already received from the server
    timer: null,
    busy: false
};

function woocs_late_prices_watch() {
    if (typeof woocs_current_currency !== 'undefined' && woocs_current_currency) {
        woocs_late_prices.page_currency = woocs_current_currency['name'];
    }

    if (typeof MutationObserver === 'undefined') {
        return;
    }

    new MutationObserver(function (mutations) {
        for (var i = 0; i < mutations.length; i++) {
            for (var j = 0; j < mutations[i].addedNodes.length; j++) {
                if (mutations[i].addedNodes[j].nodeType === 1) {
                    woocs_late_prices_take(mutations[i].addedNodes[j]);
                }
            }
        }
    }).observe(document.documentElement, {childList: true, subtree: true});
}

//the currency a price markup was rendered in; markup cached before data-price-currency existed
//is taken as rendered in the page currency
function woocs_late_prices_currency(el) {
    return el.getAttribute('data-price-currency') || woocs_late_prices.page_currency;
}

function woocs_late_prices_take(node) {
    var found = node.classList.contains('woocs_price_code') ? [node] : node.getElementsByClassName('woocs_price_code');
    if (!found.length) {
        return;
    }

    found = Array.prototype.slice.call(found);
    for (var i = 0; i < found.length; i++) {
        var el = found[i];
        var redraw_id = el.getAttribute('data-redraw-id');
        //data-live: rendered by AJAX for this visitor, nothing to redraw
        var redrawable = redraw_id && el.getAttribute('data-product-id') && !el.hasAttribute('data-live');
        var visitor = woocs_late_prices.visitor_currency;

        if (!redrawable || (visitor && woocs_late_prices_currency(el) === visitor)) {
            //no request needed: cleared synchronously, before the browser paints the spinner
            el.classList.remove('woocs_preloader_ajax');
        } else if (visitor && typeof woocs_late_prices.html[redraw_id] !== 'undefined') {
            //the same cached markup inserted again, for example a Composite option chosen twice
            jQuery(el).replaceWith(woocs_late_prices.html[redraw_id]);
        } else {
            woocs_late_prices.queue.push(el);
        }
    }

    woocs_late_prices_schedule();
}

//called by the first redraw pass with the visitor currency, or with '' when it could not tell
function woocs_late_prices_ready(visitor_currency) {
    woocs_late_prices.pending = false;
    if (visitor_currency) {
        woocs_late_prices.visitor_currency = visitor_currency;
    }
    woocs_late_prices_schedule();
}

function woocs_late_prices_schedule() {
    //while the first redraw pass is running it handles what is on the page, so late prices wait for it
    if (woocs_late_prices.pending || woocs_late_prices.timer || !woocs_late_prices.queue.length) {
        return;
    }

    //short debounce: one request for all prices a plugin inserts in one go
    woocs_late_prices.timer = setTimeout(woocs_late_prices_flush, 30);
}

function woocs_late_prices_flush() {
    woocs_late_prices.timer = null;
    if (woocs_late_prices.busy) {
        return; //called again when the running request completes
    }

    var visitor = woocs_late_prices.visitor_currency;
    var groups = {}; //rendered currency => elements
    var group_currency = '';
    for (var i = 0; i < woocs_late_prices.queue.length; i++) {
        var el = woocs_late_prices.queue[i];
        //removed from the page meanwhile, for example replaced by the first redraw pass
        if (!document.documentElement.contains(el)) {
            continue;
        }
        var currency = woocs_late_prices_currency(el);
        if (visitor && currency === visitor) {
            el.classList.remove('woocs_preloader_ajax');
            continue;
        }
        if (!groups[currency]) {
            groups[currency] = [];
        }
        if (groups[currency].indexOf(el) === -1) {
            groups[currency].push(el);
        }
        group_currency = currency;
    }
    woocs_late_prices.queue = [];

    if (!group_currency) {
        return;
    }

    //one request per rendered currency, normally there is only one; the rest waits for the next round
    var items = groups[group_currency];
    for (var c in groups) {
        if (c !== group_currency) {
            woocs_late_prices.queue = woocs_late_prices.queue.concat(groups[c]);
        }
    }

    var clear = function (list) {
        for (var i = 0; i < list.length; i++) {
            list[i].classList.remove('woocs_preloader_ajax');
        }
    };

    var products_ids = {};
    var products_currency = {};
    for (var i = 0; i < items.length; i++) {
        var redraw_id = items[i].getAttribute('data-redraw-id');
        products_ids[redraw_id] = items[i].getAttribute('data-product-id');
        if (items[i].getAttribute('data-currency')) {
            products_currency[redraw_id] = items[i].getAttribute('data-currency');
        }
    }

    woocs_late_prices.busy = true;
    jQuery.post(woocs_ajaxurl, {
        action: "woocs_get_products_price_html",
        products_ids: products_ids,
        products_currency: products_currency,
        current_currency: group_currency
    }, function (data) {
        if (typeof data === 'string') {
            data = JSON.parse(data);
        }

        //empty answer: this markup is already in the visitor currency
        if (jQuery.isEmptyObject(data) || typeof data.ids === 'undefined') {
            woocs_late_prices.visitor_currency = group_currency;
            clear(items);
            return;
        }

        woocs_late_prices.visitor_currency = data.current_currency;
        for (var i = 0; i < items.length; i++) {
            var redraw_id = items[i].getAttribute('data-redraw-id');
            if (typeof data.ids[redraw_id] !== 'undefined') {
                //the answer is rendered by AJAX (data-live, no preloader), the replace is a guard against a loop
                woocs_late_prices.html[redraw_id] = String(data.ids[redraw_id]).replace(/\bwoocs_preloader_ajax\b/g, '');
                if (document.documentElement.contains(items[i])) {
                    jQuery(items[i]).replaceWith(woocs_late_prices.html[redraw_id]);
                }
            } else {
                items[i].classList.remove('woocs_preloader_ajax');
            }
        }
    }).fail(function () {
        //never leave a spinner forever
        clear(items);
    }).always(function () {
        woocs_late_prices.busy = false;
        woocs_late_prices_schedule();
    });
}

function woocs_refresh_mini_cart(delay) {
    /** Cart Handling */
    setTimeout(function () {
        try {

            //for refreshing mini cart
            $fragment_refresh = {
                url: wc_cart_fragments_params.ajax_url,
                type: 'POST',
                data: {action: 'woocommerce_get_refreshed_fragments', woocs_woocommerce_before_mini_cart: 'mini_cart_refreshing'},
                success: function (data) {
                    if (data && data.fragments) {

                        jQuery.each(data.fragments, function (key, value) {
                            jQuery(key).replaceWith(value);
                        });

                        try {
                            if ($supports_html5_storage) {
                                sessionStorage.setItem(wc_cart_fragments_params.fragment_name, JSON.stringify(data.fragments));
                                sessionStorage.setItem('wc_cart_hash', data.cart_hash);
                            }
                        } catch (e) {

                        }

                        jQuery('body').trigger('wc_fragments_refreshed');
                    }
                }
            };

            jQuery.ajax($fragment_refresh);


            /* Cart hiding */
            try {
                if (woocs_get_cookie('woocommerce_items_in_cart') > 0)
                {
                    jQuery('.hide_cart_widget_if_empty').closest('.widget_shopping_cart').show();
                } else {
                    jQuery('.hide_cart_widget_if_empty').closest('.widget_shopping_cart').hide();
                }
            } catch (e) {
                //***
            }


            jQuery('body').on('adding_to_cart', function () {
                jQuery('.hide_cart_widget_if_empty').closest('.widget_shopping_cart').show();
            });

        } catch (e) {
            //***
        }

    }, delay);

}

function woocs_get_cookie(name) {
    var matches = document.cookie.match(new RegExp(
            "(?:^|; )" + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + "=([^;]*)"
            ));
    return matches ? decodeURIComponent(matches[1]) : undefined;
}

/*auto switcher*/

jQuery(function () {
    jQuery('.woocs_auto_switcher_link').on('click', function () {
        woocs_redirect(jQuery(this).data('currency'));
        return false;
    });

    jQuery('.woocs_auto_switcher li').on('click', function (e) {
        woocs_redirect(jQuery(this).find('a.woocs_auto_switcher_link').data('currency'));
        return false;
    });
});

function woocs_auto_switcher_redraw(curr_curr, switcher) {
    var view = switcher.data('view');
    switch (view) {
        case 'classic_blocks':
            switcher.find('a').removeClass('woocs_curr_curr');
            switcher.find('a[data-currency="' + curr_curr + '"]').addClass('woocs_curr_curr');
            break;
        case 'roll_blocks':
            switcher.find('a').removeClass('woocs_curr_curr');
            switcher.find('li').removeClass('woocs_auto_bg_woocs_curr_curr');
            var current_link = switcher.find('a[data-currency="' + curr_curr + '"]');
            current_link.addClass('woocs_curr_curr');
            current_link.parents('li').addClass('woocs_auto_bg_woocs_curr_curr');
            break;
        case 'round_select':
            switcher.find('a').removeClass('woocs_curr_curr');
            var current_link = switcher.find('a[data-currency="' + curr_curr + '"]');
            current_link.addClass('woocs_curr_curr');
            jQuery('.woocs_current_text').html(current_link.find('.woocs_base_text').html());
            break;
        default:
            break;
    }

}

function woocs_remove_link_param(key, sourceURL) {
    var rtn = sourceURL.split("?")[0],
            param,
            params_arr = [],
            queryString = (sourceURL.indexOf("?") !== -1) ? sourceURL.split("?")[1] : "";
    if (queryString !== "") {
        params_arr = queryString.split("&");
        for (var i = params_arr.length - 1; i >= 0; i -= 1) {
            param = params_arr[i].split("=")[0];
            if (param === key) {
                params_arr.splice(i, 1);
            }
        }
        rtn = rtn + "?" + params_arr.join("&");
    }
    return rtn;
}

function woocs_init_ddslick_select() {
    jQuery.each(jQuery('select.woocommerce-currency-switcher').not('.woocs_clean_select'), function (index, obj) {
        var width = jQuery(obj).data('width');
        var flag_position = jQuery(obj).data('flag-position');
        jQuery(obj).ddslick({
            //data: ddData,
            width: width,
            imagePosition: flag_position,
            selectText: "Select currency",
            //background:'#ff0000',
            onSelected: function (data) {
                if (!woocs_loading_first_time)
                {
                    var form = jQuery(data.selectedItem).closest('form.woocommerce-currency-switcher-form');
                    jQuery(form).find('input[name="woocommerce-currency-switcher"]').eq(0).val(data.selectedData.value);

                    if (Object.keys(woocs_array_of_get).length == 0) {
                        //jQuery(form).submit();
                        woocs_redirect(data.selectedData.value);
                    } else {
                        woocs_redirect(data.selectedData.value);
                    }
                }

            }
        });
    });
}
