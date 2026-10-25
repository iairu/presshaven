<?php
/*
Plugin Name: Google Language Translator
Plugin URI: https://gtranslate.io/?xyz=3167
Version: 7.0.2
Description: The MOST SIMPLE Google Translator plugin. This plugin adds Google Translator to your website by using a single shortcode, [google-translator]. Settings include: layout style, hide/show specific languages. Add the shortcode to pages, posts, and widgets.
Author: Translate AI Multilingual Solutions
Author URI: https://gtranslate.io
License: GPLv2 or later
Text Domain: google-language-translator
*/

if(!defined('ABSPATH'))
    exit;

define('GLT_VERSION', '7.0.2');

include(plugin_dir_path( __FILE__ ) . 'widget.php');

class google_language_translator {

  public $languages_array;

  public function __construct() {

    $this->languages_array = array (
      'af' => 'Afrikaans',
      'sq' => 'Albanian',
      'am' => 'Amharic',
      'ar' => 'Arabic',
      'hy' => 'Armenian',
      'az' => 'Azerbaijani',
      'eu' => 'Basque',
      'be' => 'Belarusian',
      'bn' => 'Bengali',
      'bs' => 'Bosnian',
      'bg' => 'Bulgarian',
      'ca' => 'Catalan',
      'ceb' => 'Cebuano',
      'ny' => 'Chichewa',
      'zh-CN' => 'Chinese (Simplified)',
      'zh-TW' => 'Chinese (Traditional)',
      'co' => 'Corsican',
      'hr' => 'Croatian',
      'cs' => 'Czech',
      'da' => 'Danish',
      'nl' => 'Dutch',
      'en' => 'English',
      'eo' => 'Esperanto',
      'et' => 'Estonian',
      'tl' => 'Filipino',
      'fi' => 'Finnish',
      'fr' => 'French',
      'fy' => 'Frisian',
      'gl' => 'Galician',
      'ka' => 'Georgian',
      'de' => 'German',
      'el' => 'Greek',
      'gu' => 'Gujarati',
      'ht' => 'Haitian',
      'ha' => 'Hausa',
      'haw' => 'Hawaiian',
      'iw' => 'Hebrew',
      'hi' => 'Hindi',
      'hmn' => 'Hmong',
      'hu' => 'Hungarian',
      'is' => 'Icelandic',
      'ig' => 'Igbo',
      'id' => 'Indonesian',
      'ga' => 'Irish',
      'it' => 'Italian',
      'ja' => 'Japanese',
      'jw' => 'Javanese',
      'kn' => 'Kannada',
      'kk' => 'Kazakh',
      'km' => 'Khmer',
      'ko' => 'Korean',
      'ku' => 'Kurdish',
      'ky' => 'Kyrgyz',
      'lo' => 'Lao',
      'la' => 'Latin',
      'lv' => 'Latvian',
      'lt' => 'Lithuanian',
      'lb' => 'Luxembourgish',
      'mk' => 'Macedonian',
      'mg' => 'Malagasy',
      'ml' => 'Malayalam',
      'ms' => 'Malay',
      'mt' => 'Maltese',
      'mi' => 'Maori',
      'mr' => 'Marathi',
      'mn' => 'Mongolian',
      'my' => 'Myanmar (Burmese)',
      'ne' => 'Nepali',
      'no' => 'Norwegian',
      'ps' => 'Pashto',
      'fa' => 'Persian',
      'pl' => 'Polish',
      'pt' => 'Portuguese',
      'pa' => 'Punjabi',
      'ro' => 'Romanian',
      'ru' => 'Russian',
      'sr' => 'Serbian',
      'sn' => 'Shona',
      'st' => 'Sesotho',
      'sd' => 'Sindhi',
      'si' => 'Sinhala',
      'sk' => 'Slovak',
      'sl' => 'Slovenian',
      'sm' => 'Samoan',
      'gd' => 'Scots Gaelic',
      'so' => 'Somali',
      'es' => 'Spanish',
      'su' => 'Sundanese',
      'sw' => 'Swahili',
      'sv' => 'Swedish',
      'tg' => 'Tajik',
      'ta' => 'Tamil',
      'te' => 'Telugu',
      'th' => 'Thai',
      'tr' => 'Turkish',
      'uk' => 'Ukrainian',
      'ur' => 'Urdu',
      'uz' => 'Uzbek',
      'vi' => 'Vietnamese',
      'cy' => 'Welsh',
      'xh' => 'Xhosa',
      'yi' => 'Yiddish',
      'yo' => 'Yoruba',
      'zu' => 'Zulu',
    );

    $plugin_data = get_file_data(__FILE__, array('Version' => 'Version'), false);
    define('PLUGIN_VER', $plugin_data['Version']);

    register_activation_hook( __FILE__, array(&$this,'glt_activate'));
    register_deactivation_hook( __FILE__, array(&$this,'glt_deactivate'));

    add_action( 'admin_menu', array( &$this, 'add_my_admin_menus'));
    add_action('admin_init',array(&$this, 'initialize_settings'));
    add_action('wp_head',array(&$this, 'load_css'));
    add_action('wp_footer',array(&$this, 'footer_script'));
    add_action('send_headers', array(&$this, 'set_dns_prefetch_header'));
    add_shortcode( 'google-translator',array(&$this, 'google_translator_shortcode'));
    add_shortcode( 'glt', array(&$this, 'google_translator_menu_language'));
    add_filter('widget_text','do_shortcode');
    add_filter('walker_nav_menu_start_el', array(&$this,'menu_shortcodes') , 10 , 2);
    add_filter( 'plugin_action_links_' . plugin_basename(__FILE__), array(&$this, 'glt_settings_link') );

    if (!is_admin()) {
      add_action('wp_enqueue_scripts',array(&$this, 'flags'));
    }

    // phpcs:disable PluginCheck.CodeAnalysis.WriteFile.PluginDirectoryWrite -- Writing configuration to a local file is intentional here to avoid repeated database I/O
    // make sure main_lang is set correctly in config.php file
    global $glt_url_structure, $glt_seo_active;
    if($glt_seo_active == '1' and $glt_url_structure == 'sub_directory') {
        include dirname(__FILE__) . '/url_addon/config.php';

        $default_language = get_option('googlelanguagetranslator_language');
        if($main_lang != $default_language) { // update main_lang in config.php
            $config_file = dirname(__FILE__) . '/url_addon/config.php';
            if(is_readable($config_file) and wp_is_writable($config_file)) {
                $config = file_get_contents($config_file);
                if(strpos($config, 'main_lang') !== false) {
                    $config = preg_replace('/\$main_lang = \'[a-z-]{2,5}\'/i', '$main_lang = \''.$default_language.'\'', $config);
                    if(is_string($config) and strlen($config) > 10)
                        file_put_contents($config_file, $config);
                }
            }
        }
    }
  }

  public function glt_activate() {
    add_option('googlelanguagetranslator_active', 1);
    add_option('googlelanguagetranslator_language','en');
    add_option('googlelanguagetranslator_flags', 1);
    add_option('language_display_settings',array ('en' => 1));
    add_option('googlelanguagetranslator_translatebox','yes');
    add_option('googlelanguagetranslator_display','Vertical');
    add_option('googlelanguagetranslator_flags_alignment','flags_left');
    add_option('googlelanguagetranslator_css','');
    add_option('googlelanguagetranslator_floating_widget','yes');
    add_option('googlelanguagetranslator_flag_size','18');
    add_option('googlelanguagetranslator_flags_order','');
    add_option('googlelanguagetranslator_english_flag_choice','');
    add_option('googlelanguagetranslator_spanish_flag_choice','');
    add_option('googlelanguagetranslator_portuguese_flag_choice','');
    add_option('googlelanguagetranslator_floating_widget_text', 'Translate &raquo;');
    add_option('googlelanguagetranslator_floating_widget_text_allow_translation', 0);
    delete_option('googlelanguagetranslator_manage_translations',0);
    delete_option('flag_display_settings');
  }

  public function glt_deactivate() {
    delete_option('flag_display_settings');
    delete_option('googlelanguagetranslator_language_option');
  }

  public function glt_settings_link ( $links ) {
    $settings_link = array(
      '<a href="' . admin_url( 'options-general.php?page=google_language_translator' ) . '">Settings</a>',
    );
   return array_merge( $links, $settings_link );
  }

  public function add_my_admin_menus(){
    $p = add_options_page('Google Language Translator', 'Google Language Translator', 'manage_options', 'google_language_translator', array(&$this, 'page_layout_cb'));

    add_action( 'load-' . $p, array(&$this, 'load_admin_js' ));
  }

  public function load_admin_js(){
    add_action( 'admin_enqueue_scripts', array(&$this, 'enqueue_admin_js' ));
    add_action('admin_footer',array(&$this, 'footer_script'));
  }

  public function enqueue_admin_js(){
    wp_enqueue_script( 'jquery-ui-core');
    wp_enqueue_script( 'jquery-ui-sortable');
    wp_enqueue_style( 'wp-color-picker' );
    wp_enqueue_script( 'scripts-admin', plugins_url('js/scripts-admin.js',__FILE__), array('jquery', 'wp-color-picker'), PLUGIN_VER, true);
    wp_enqueue_script( 'scripts', plugins_url('js/scripts.js',__FILE__), array('jquery', 'wp-color-picker'), PLUGIN_VER, true);

    wp_enqueue_style( 'style.css', plugins_url('css/style.css', __FILE__),'', PLUGIN_VER,'');

    if (get_option ('googlelanguagetranslator_floating_widget') == 'yes') {
      wp_enqueue_style( 'glt-toolbar-styles', plugins_url('css/toolbar.css', __FILE__),'', PLUGIN_VER,'' );
    }
  }

  public function flags() {
    wp_enqueue_script( 'scripts', plugins_url('js/scripts.js',__FILE__), array('jquery'), PLUGIN_VER, true);
    wp_enqueue_style( 'google-language-translator', plugins_url('css/style.css', __FILE__), '', PLUGIN_VER, '');

    if (get_option ('googlelanguagetranslator_floating_widget') == 'yes') {
      wp_enqueue_style( 'glt-toolbar-styles', plugins_url('css/toolbar.css', __FILE__), '', PLUGIN_VER, '');
    }
  }

  public function load_css() {
    include( plugin_dir_path( __FILE__ ) . '/css/style.php');
  }

  public function google_translator_shortcode() {
    if(get_option('googlelanguagetranslator_display') == 'Vertical' or get_option('googlelanguagetranslator_display') == 'SIMPLE')
        return $this->googlelanguagetranslator_switcher('vertical');
    elseif(get_option('googlelanguagetranslator_display') == 'Horizontal')
        return $this->googlelanguagetranslator_switcher('horizontal');
  }

  public function googlelanguagetranslator_included_languages() {
    $get_language_choices = get_option ('language_display_settings');

    foreach ($get_language_choices as $key=>$value):
      if ($value == 1):
        $items[] = $key;
      endif;
    endforeach;

    $comma_separated = implode(",",array_values($items));
    $lang = ", includedLanguages:'".$comma_separated."'";
    return $lang;
  }

  public function menu_shortcodes( $item_output,$item ) {
    if ( !empty($item->description)) {
      $output = do_shortcode($item->description);

      if ( $output != $item->description )
        $item_output = $output;
      }
    return $item_output;
  }

  public function google_translator_menu_language($atts, $content = '') {
    extract(shortcode_atts(array(
      "language" => 'Spanish',
      "label" => 'Spanish',
      "image" => 'no',
      "text" => 'yes',
      "image_size" => '24',
      "label" => html_entity_decode('Espa&ntilde;ol')
    ), $atts));

    $glt_url_structure = get_option('googlelanguagetranslator_url_structure');
    $glt_seo_active = get_option('googlelanguagetranslator_seo_active');
    $default_language = get_option('googlelanguagetranslator_language');
    $english_flag_choice = get_option('googlelanguagetranslator_english_flag_choice');
    $spanish_flag_choice = get_option('googlelanguagetranslator_spanish_flag_choice');
    $portuguese_flag_choice = get_option('googlelanguagetranslator_portuguese_flag_choice');
    $language_code = array_search($language,$this->languages_array);
    $language_name = $language;
    $language_name_flag = $language_name;

    if ( $language_name == 'English' && $english_flag_choice == 'canadian_flag') {
      $language_name_flag = 'canada';
    }
    if ( $language_name == "English" && $english_flag_choice == 'us_flag') {
          $language_name_flag = 'united-states';
    }
    if ( $language_name == 'Spanish' && $spanish_flag_choice == 'mexican_flag') {
      $language_name_flag = 'mexico';
    }
    if ( $language_name == 'Portuguese' && $portuguese_flag_choice == 'brazilian_flag') {
      $language_name_flag = 'brazil';
    }

    $href = '#';
    if($glt_seo_active == '1') {
        $current_url = network_home_url(add_query_arg(null, null));
        switch($glt_url_structure) {
            case 'sub_directory':
                $href = ($language_code == $default_language) ? $current_url : '/' . $language_code . $_SERVER['REQUEST_URI'];
                break;
            case 'sub_domain':
                $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);
                $href = ($language_code == $default_language) ? $current_url : str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $language_code . '.' . $domain, $current_url);
                break;
            default:
                break;
        }
    }

    return "<a href='".esc_url($href)."' class='nturl notranslate ".esc_attr($language_code)." ".esc_attr($language_name_flag)." single-language flag' title='".esc_attr($language)."'>".($image=='yes' ? "<span class='flag size".esc_attr($image_size)."'></span>" : '') .($text=='yes' ? htmlspecialchars($label) : '')."</a>";
  }

  public function footer_script() {
    global $vertical, $horizontal;

    $layout = get_option('googlelanguagetranslator_display');
    if($layout == 'SIMPLE')
        $layout = 'Vertical';

    $default_language = get_option('googlelanguagetranslator_language');
    $new_languages_array_string = get_option('googlelanguagetranslator_flags_order');
    $new_languages_array = explode(',', $new_languages_array_string);
    $new_languages_array_codes = array_values($new_languages_array);
    $new_languages_array_count = count($new_languages_array);
    $english_flag_choice = get_option('googlelanguagetranslator_english_flag_choice');
    $spanish_flag_choice = get_option('googlelanguagetranslator_spanish_flag_choice');
    $portuguese_flag_choice = get_option('googlelanguagetranslator_portuguese_flag_choice');
    $show_flags = get_option('googlelanguagetranslator_flags');
    $flag_width = get_option('googlelanguagetranslator_flag_size');
    $get_language_choices = get_option('language_display_settings');
    $floating_widget = get_option('googlelanguagetranslator_floating_widget');
    $floating_widget_text = get_option('googlelanguagetranslator_floating_widget_text');
    $floating_widget_text_translation_allowed = get_option('googlelanguagetranslator_floating_widget_text_allow_translation');
    $is_active = get_option('googlelanguagetranslator_active');
    $glt_url_structure = get_option('googlelanguagetranslator_url_structure');
    $glt_seo_active = get_option('googlelanguagetranslator_seo_active');

    $str = '';

    // build one flag item
    $build_flag_item = function ($language_code, $language_name) use ($english_flag_choice, $spanish_flag_choice, $portuguese_flag_choice, $default_language, $glt_url_structure, $glt_seo_active) {
        $language_name_flag = $language_name;

        if($language_name == 'English' and $english_flag_choice == 'canadian_flag')
            $language_name_flag = 'canada';

        if($language_name == 'English' and $english_flag_choice == 'us_flag')
            $language_name_flag = 'united-states';

        if($language_name == 'Spanish' and $spanish_flag_choice == 'mexican_flag')
            $language_name_flag = 'mexico';

        if($language_name == 'Portuguese' and $portuguese_flag_choice == 'brazilian_flag')
            $language_name_flag = 'brazil';

        $href = '#';

        if($glt_seo_active == '1') {
            $current_url = network_home_url(add_query_arg(null, null));

            switch($glt_url_structure) {
                case 'sub_directory':
                    if($language_code == $default_language)
                        $href = $current_url;
                    else
                        $href = '/' . $language_code . $_SERVER['REQUEST_URI'];
                    break;

                case 'sub_domain':
                    $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);
                    if($language_code == $default_language)
                        $href = $current_url;
                    else
                        $href = str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $language_code . '.' . $domain, $current_url);
                    break;
            }
        }

        return '<li id="' . esc_attr($language_name) . '"><a href="' . esc_url($href) . '" title="' . esc_attr($language_name) . '" class="nturl notranslate ' . esc_attr($language_code) . ' flag ' . esc_attr($language_name_flag) . '"></a><</li>';
    };

    if($is_active == 1) {
        if($floating_widget == 'yes') {
            $text_class = 'notranslate';

            if($floating_widget_text_translation_allowed == 1)
                $text_class = 'translate';

            $button_text = 'Translate &raquo;';

            if(!empty($floating_widget_text))
                $button_text = $floating_widget_text;

            $str .= '<div id="glt-translate-trigger">';
            $str .= '<span class="' . esc_attr($text_class) . '">';
            $str .= esc_html($button_text);
            $str .= '</span></div>';
            $str .= '<div id="glt-toolbar"></div>';
        }

        $needs_vertical_flags = $layout == 'Vertical' && !isset($vertical);
        $needs_horizontal_flags = $layout == 'Horizontal' && !isset($horizontal);
        $needs_hidden_flags = $show_flags == 0 && (isset($vertical) || isset($horizontal));

        if($needs_vertical_flags or $needs_horizontal_flags or $needs_hidden_flags) {
            $str .= '<div id="flags" style="display:none" class="size' . esc_attr($flag_width) . '">';
            $str .= '<ul id="sortable" class="ui-sortable">';

            if(empty($new_languages_array_string)) {
                // no saved order: include only enabled languages
                foreach($this->languages_array as $language_code => $language_name) {
                    if(!empty($get_language_choices[$language_code]) and $get_language_choices[$language_code] == 1)
                        $str .= $build_flag_item($language_code, $language_name);
                }
            } elseif($new_languages_array_count != count($get_language_choices)) {
                // count mismatch: including every entry in the language settings
                foreach($get_language_choices as $language_code => $value) {
                    $language_name = $this->languages_array[$language_code];
                    $str .= $build_flag_item($language_code, $language_name);
                }
            } else {
                // use the saved language-name order
                foreach($new_languages_array_codes as $language_name) {
                    $language_code = array_search($language_name, $this->languages_array);
                    $str .= $build_flag_item($language_code, $language_name);
                }
            }

            $str .= '</ul>';
            $str .= '</div>';
        }
    }

    if($glt_seo_active != '1') {
        $str .= '<div id="glt-footer">';
        if(!isset($vertical) and !isset($horizontal))
            $str .= '<div id="google_language_translator" class="default-language-' . esc_attr($default_language) . '"></div>';
        $str .= '</div>';

        wp_enqueue_script('glt_widget_script', 'https://cdn.gtranslate.net/widgets/latest/dropdown.js', array(), GLT_VERSION, true);
        wp_add_inline_script('glt_widget_script', 'window.gtranslateSettings = /* document.write */ {"default_language": "'.esc_attr($default_language).'", "languages": '.wp_json_encode(array_keys($get_language_choices)).', "wrapper_selector": "#google_language_translator"}', 'before');
    }

    echo wp_kses_post($str);
  }

  public function set_dns_prefetch_header() {
      header('Link: <https://cdn.gtranslate.net/>; rel=dns-prefetch', false);
  }

  public function googlelanguagetranslator_switcher($dir) {
    global $vertical;
    global $horizontal;

    if($dir == 'vertical')
        $vertical = 1;
    if($dir == 'horizontal')
        $horizontal = 1;

    $new_languages_array_string = get_option('googlelanguagetranslator_flags_order');
    $new_languages_array = explode(",",$new_languages_array_string);
    $new_languages_array_codes = array_values($new_languages_array);
    $new_languages_array_count = count($new_languages_array);
    $get_language_choices = get_option ('language_display_settings');
    $show_flags = get_option('googlelanguagetranslator_flags');
    $flag_width = get_option('googlelanguagetranslator_flag_size');
    $default_language_code = get_option('googlelanguagetranslator_language');
    $english_flag_choice = get_option('googlelanguagetranslator_english_flag_choice');
    $spanish_flag_choice = get_option('googlelanguagetranslator_spanish_flag_choice');
    $portuguese_flag_choice = get_option('googlelanguagetranslator_portuguese_flag_choice');
    $is_active = get_option ( 'googlelanguagetranslator_active' );
    $language_choices = $this->googlelanguagetranslator_included_languages();
    $floating_widget = get_option ('googlelanguagetranslator_floating_widget');
    $glt_url_structure = get_option('googlelanguagetranslator_url_structure');
    $glt_seo_active = get_option('googlelanguagetranslator_seo_active');

    $default_language = $default_language_code;
    $str = '';

    if ($is_active==1):
      if ($show_flags==1):
      $str.='<div id="flags" class="size'.$flag_width.'">';
      $str.='<ul id="sortable" class="ui-sortable" style="float:left">';

      if (empty($new_languages_array_string)):
        foreach ($this->languages_array as $key=>$value) {
          $language_code = $key;
          $language_name = $value;
          $language_name_flag = $language_name;

          if (!empty($get_language_choices[$language_code]) && $get_language_choices[$language_code]==1) {
            if ( $language_name == 'English' && $english_flag_choice == 'canadian_flag') {
              $language_name_flag = 'canada';
            }
            if ( $language_name == "English" && $english_flag_choice == 'us_flag') {
              $language_name_flag = 'united-states';
            }
            if ( $language_name == 'Spanish' && $spanish_flag_choice == 'mexican_flag') {
              $language_name_flag = 'mexico';
            }
            if ( $language_name == 'Portuguese' && $portuguese_flag_choice == 'brazilian_flag') {
              $language_name_flag = 'brazil';
            }

            $href = '#';
            if($glt_seo_active == '1') {
                $current_url = network_home_url(add_query_arg(null, null));
                switch($glt_url_structure) {
                    case 'sub_directory':
                        $href = ($language_code == $default_language) ? $current_url : '/' . $language_code . $_SERVER['REQUEST_URI'];
                        break;
                    case 'sub_domain':
                        $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);
                        $href = ($language_code == $default_language) ? $current_url : str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $language_code . '.' . $domain, $current_url);
                        break;
                    default:
                        break;
                }
            }

            $str.="<li id='".$language_name."'><a href='".esc_url($href)."' title='".$language_name."' class='nturl notranslate ".$language_code." flag ".$language_name_flag."'></a></li>";
          } //endif
        }//foreach
      else:
        if ($new_languages_array_count != count($get_language_choices)):
            foreach ($get_language_choices as $key => $value) {
              $language_code = $key;
              $language_name = $this->languages_array[$key];
              $language_name_flag = $language_name;

              if ( $language_name == 'English' && $english_flag_choice == 'canadian_flag') {
                $language_name_flag = 'canada';
              }
              if ( $language_name == "English" && $english_flag_choice == 'us_flag') {
                $language_name_flag = 'united-states';
              }
              if ( $language_name == 'Spanish' && $spanish_flag_choice == 'mexican_flag') {
                $language_name_flag = 'mexico';
              }
              if ( $language_name == 'Portuguese' && $portuguese_flag_choice == 'brazilian_flag') {
                $language_name_flag = 'brazil';
              }

              $href = '#';
              if($glt_seo_active == '1') {
                  $current_url = network_home_url(add_query_arg(null, null));
                  switch($glt_url_structure) {
                    case 'sub_directory':
                        $href = ($language_code == $default_language) ? $current_url : '/' . $language_code . $_SERVER['REQUEST_URI'];
                        break;
                    case 'sub_domain':
                        $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);
                        $href = ($language_code == $default_language) ? $current_url : str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $language_code . '.' . $domain, $current_url);
                        break;
                    default:
                        break;
                  }
              }

              $str.='<li id="'.$language_name.'"><a href="'.esc_url($href).'" title="'.$language_name.'" class="nturl notranslate '.$language_code.' flag '.$language_name_flag.'"></a></li>';
            } //foreach
          else:
            foreach ($new_languages_array_codes as $value) {
              $language_name = $value;
              $language_code = array_search ($language_name, $this->languages_array);
              $language_name_flag = $language_name;

              if ( $language_name == 'English' && $english_flag_choice == 'canadian_flag') {
                $language_name_flag = 'canada';
              }
              if ( $language_name == "English" && $english_flag_choice == 'us_flag') {
                $language_name_flag = 'united-states';
              }
              if ( $language_name == 'Spanish' && $spanish_flag_choice == 'mexican_flag') {
                $language_name_flag = 'mexico';
              }
              if ( $language_name == 'Portuguese' && $portuguese_flag_choice == 'brazilian_flag') {
                $language_name_flag = 'brazil';
              }

              $href = '#';
              if($glt_seo_active == '1') {
                  $current_url = network_home_url(add_query_arg(null, null));
                  switch($glt_url_structure) {
                    case 'sub_directory':
                        $href = ($language_code == $default_language) ? $current_url : '/' . $language_code . $_SERVER['REQUEST_URI'];
                        break;
                    case 'sub_domain':
                        $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);
                        $href = ($language_code == $default_language) ? $current_url : str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $language_code . '.' . $domain, $current_url);
                        break;
                    default:
                        break;
                  }
              }

              $str.='<li id="'.$language_name.'"><a href="'.esc_url($href).'" title="'.$language_name.'" class="nturl notranslate '.$language_code.' flag '.$language_name_flag.'"></a></li>';
            }//foreach
          endif;
      endif;

      $str.='</ul>';
      $str.='</div>';

      endif; //show_flags

      if($glt_seo_active == '1') {
          $str .= '<div id="google_language_translator" class="default-language-'.$default_language_code.'">';
          $str .= '<select aria-label="Website Language Selector" class="notranslate"><option value="">Select Language</option>';

          $get_language_choices = get_option ('language_display_settings');
          foreach($get_language_choices as $key => $value) {
              if($value == 1)
                  $str .= '<option value="'.$default_language.'|'.$key.'">'.$this->languages_array[$key].'</option>';
          }
          $str .= '</select></div>';

          $str .= '<script>';
          if($glt_url_structure == 'sub_directory') {
              $str .= "function doGLTTranslate(lang_pair) {if(lang_pair.value)lang_pair=lang_pair.value;if(lang_pair=='')return;var lang=lang_pair.split('|')[1];if(typeof _gaq!='undefined'){_gaq.push(['_trackEvent', 'GTranslate', lang, location.pathname+location.search]);}else {if(typeof ga!='undefined')ga('send', 'event', 'GTranslate', lang, location.pathname+location.search);}var plang=location.pathname.split('/')[1];if(plang.length !=2 && plang != 'zh-CN' && plang != 'zh-TW' && plang != 'hmn' && plang != 'haw' && plang != 'ceb')plang='$default_language';if(lang == '$default_language')location.href=location.protocol+'//'+location.host+glt_request_uri;else location.href=location.protocol+'//'+location.host+'/'+lang+glt_request_uri;}";
          } elseif($glt_url_structure == 'sub_domain') {
              $str .= "function doGLTTranslate(lang_pair) {if(lang_pair.value)lang_pair=lang_pair.value;if(lang_pair=='')return;var lang=lang_pair.split('|')[1];if(typeof _gaq!='undefined'){_gaq.push(['_trackEvent', 'GTranslate', lang, location.hostname+location.pathname+location.search]);}else {if(typeof ga!='undefined')ga('send', 'event', 'GTranslate', lang, location.hostname+location.pathname+location.search);}var plang=location.hostname.split('.')[0];if(plang.length !=2 && plang.toLowerCase() != 'zh-cn' && plang.toLowerCase() != 'zh-tw' && plang != 'hmn' && plang != 'haw' && plang != 'ceb')plang='$default_language';location.href=location.protocol+'//'+(lang == '$default_language' ? '' : lang+'.')+location.hostname.replace('www.', '').replace(RegExp('^' + plang + '[.]'), '')+glt_request_uri;}";
          }
          $str .= '</script>';

      } else
          $str.='<div id="google_language_translator" class="default-language-'.$default_language_code.'"></div>';

      return $str;

    endif;
  }

  public function initialize_settings() {
    add_settings_section('glt_settings', 'Settings', '', 'google_language_translator');

    $settings = array(
        // Checkboxes.
        'googlelanguagetranslator_active' => 'absint',
        'googlelanguagetranslator_flags' => 'absint',
        'googlelanguagetranslator_floating_widget_text_allow_translation' => 'absint',
        'googlelanguagetranslator_seo_active' => 'absint',
        'googlelanguagetranslator_url_translation_active' => 'absint',
        'googlelanguagetranslator_hreflang_tags_active' => 'absint',

        // Language code. Keep case for zh-CN / zh-TW.
        'googlelanguagetranslator_language' => 'sanitize_text_field',

        // Associative checkbox array.
        'language_display_settings' => function( $value ) {
            if ( ! is_array( $value ) ) {
                return array();
            }

            $value = array_intersect_key(
                $value,
                $this->languages_array
            );

            return array_map( 'absint', $value );
        },

        // yes / no selects.
        'googlelanguagetranslator_translatebox' => 'sanitize_key',
        'googlelanguagetranslator_floating_widget' => 'sanitize_key',

        // Case-sensitive values: Vertical / Horizontal / SIMPLE.
        'googlelanguagetranslator_display' => 'sanitize_text_field',

        // 100%, 150px, etc.
        'glt_language_switcher_width' => 'sanitize_text_field',

        // Colors.
        'glt_language_switcher_text_color' => 'sanitize_hex_color',
        'glt_language_switcher_bg_color' => 'sanitize_hex_color',
        'glt_floating_widget_text_color' => 'sanitize_hex_color',
        'glt_floating_widget_bg_color' => 'sanitize_hex_color',

        // flags_left / flags_right.
        'googlelanguagetranslator_flags_alignment' => 'sanitize_key',

        // Custom CSS.
        'googlelanguagetranslator_css' => 'wp_kses_post',

        // Numeric selector.
        'googlelanguagetranslator_flag_size' => 'absint',

        // Comma-separated language names.
        'googlelanguagetranslator_flags_order' => 'sanitize_text_field',

        // Flag selectors.
        'googlelanguagetranslator_english_flag_choice' => 'sanitize_key',
        'googlelanguagetranslator_spanish_flag_choice' => 'sanitize_key',
        'googlelanguagetranslator_portuguese_flag_choice' => 'sanitize_key',

        // Plain text.
        'googlelanguagetranslator_floating_widget_text' => 'sanitize_text_field',

        // bottom_left, top_right, etc.
        'glt_floating_widget_position' => 'sanitize_key',

        // sub_domain / sub_directory.
        'googlelanguagetranslator_url_structure' => 'sanitize_key',
    );

    foreach ( $settings as $setting => $sanitize_callback ) {
        add_settings_field(
            $setting,
            '',
            $setting . '_cb',
            'google_language_translator',
            'glt_settings'
        );

        register_setting(
            'google_language_translator',
            $setting,
            array(
                'sanitize_callback' => $sanitize_callback,
            )
        );
    }
  }

  public function googlelanguagetranslator_active_cb() {
    $option_name = 'googlelanguagetranslator_active';
    $new_value   = 1;

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = absint( get_option( $option_name ) );
    ?>
    <input
        type="checkbox"
        name="googlelanguagetranslator_active"
        id="googlelanguagetranslator_active"
        value="1"
        <?php checked( 1, $options ); ?>
    />
    &nbsp;
    <?php esc_html_e( 'Check this box to activate', 'google-language-translator' ); ?>
    <?php
  }

  public function googlelanguagetranslator_language_cb() {

    $option_name = 'googlelanguagetranslator_language';
    $new_value = 'en';

      if ( get_option( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
      }

      $options = get_option (''.$option_name.''); ?>

      <select name="googlelanguagetranslator_language" id="googlelanguagetranslator_language">

      <?php

        foreach ($this->languages_array as $key => $value) {
          $language_code = $key;
          $language_name = $value; ?>
            <option value="<?php echo esc_attr($language_code); ?>" <?php if($options==''.$language_code.''){echo "selected";}?>><?php echo esc_html($language_name); ?></option>
          <?php } ?>
      </select>
    <?php
    }

    public function language_display_settings_cb() {
      $default_language_code = get_option('googlelanguagetranslator_language');
      $option_name = 'language_display_settings';
      $new_value = array(''.$default_language_code.'' => 1);

      if ( get_option( $option_name ) == false ) {
        // The option does not exist, so we update it.
        update_option( $option_name, $new_value );
      }

      $get_language_choices = get_option (''.$option_name.''); ?>

      <script>jQuery(document).ready(function($) { $('.select-all-languages').on('click',function(e) { e.preventDefault(); $('.languages').find('input:checkbox').prop('checked', true); }); $('.clear-all-languages').on('click',function(e) { e.preventDefault();
$('.languages').find('input:checkbox').prop('checked', false); }); }); </script>

      <?php

      foreach ($this->languages_array as $key => $value) {
        $language_code = $key;
        $language_name = $value;
        $language_code_array[] = $key;

        if (!isset($get_language_choices[''.$language_code.''])) {
          $get_language_choices[''.$language_code.''] = 0;
        }

        $items[] = $get_language_choices[''.$language_code.''];
        $language_codes = $language_code_array;
        $item_count = count($items);

        if ($item_count == 1 || $item_count == 27 || $item_count == 53 || $item_count == 79) { ?>
          <div class="languages" style="width:25%; float:left">
        <?php } ?>
          <div><input type="checkbox" name="language_display_settings[<?php echo esc_attr($language_code); ?>]" value="1"<?php checked( 1,$get_language_choices[''.$language_code.'']); ?>/><?php echo esc_html($language_name); ?></div>
        <?php
        if ($item_count == 26 || $item_count == 52 || $item_count == 78 || $item_count == 104) { ?>
          </div>
        <?php }
      } ?>
     <div class="clear"></div>
    <?php
    }

    public function googlelanguagetranslator_flags_cb() {
        $option_name = 'googlelanguagetranslator_flags';
        $new_value   = 1;

        if ( false === get_option( $option_name ) ) {
            update_option( $option_name, $new_value );
        }

        $options = absint( get_option( $option_name ) );
        ?>
        <input
            type="checkbox"
            name="googlelanguagetranslator_flags"
            id="googlelanguagetranslator_flags"
            value="1"
            <?php checked( 1, $options ); ?>
        />
        &nbsp;
        <?php esc_html_e( 'Check to show flags', 'google-language-translator' ); ?>
        <?php
    }

  public function googlelanguagetranslator_floating_widget_cb() {

    $option_name = 'googlelanguagetranslator_floating_widget' ;
    $new_value = 'yes';

      if ( get_option( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
      }

      $options = get_option (''.$option_name.''); ?>

          <select name="googlelanguagetranslator_floating_widget" id="googlelanguagetranslator_floating_widget" style="width:170px">
              <option value="yes" <?php if($options=='yes'){echo "selected";}?>>Yes, show widget</option>
              <option value="no" <?php if($options=='no'){echo "selected";}?>>No, hide widget</option>
          </select>
  <?php }

  public function googlelanguagetranslator_floating_widget_text_cb() {

    $option_name = 'googlelanguagetranslator_floating_widget_text' ;
    $new_value = 'Translate &raquo;';

    if ( get_option( $option_name ) === false ) {
      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
    }

    $options = get_option (''.$option_name.''); ?>

    <input type="text" name="googlelanguagetranslator_floating_widget_text" id="googlelanguagetranslator_floating_widget_text" value="<?php echo esc_attr($options); ?>" style="width:170px"/>

  <?php }

  public function googlelanguagetranslator_floating_widget_text_allow_translation_cb() {
    $option_name = 'googlelanguagetranslator_floating_widget_text_allow_translation';
    $new_value   = 0;

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = absint( get_option( $option_name ) );
    ?>
    <input
        type="checkbox"
        name="googlelanguagetranslator_floating_widget_text_allow_translation"
        id="googlelanguagetranslator_floating_widget_text_allow_translation"
        value="1"
        <?php checked( 1, $options ); ?>
    />
    &nbsp;
    <?php esc_html_e( 'Check to allow', 'google-language-translator' ); ?>
    <?php
  }

  public function glt_floating_widget_position_cb() {
      $option_name = 'glt_floating_widget_position';
      $new_value = '';

      if (get_option($option_name) === false):
        update_option($option_name, $new_value);
      endif;

      $options = get_option(''.$option_name.''); ?>

      <select name="glt_floating_widget_position" id="glt_floating_widget_position" style="width:170px">
        <option value="bottom_left" <?php if($options=='bottom_left'){echo "selected";}?>>Bottom left</option>
        <option value="bottom_center" <?php if($options=='bottom_center'){echo "selected";}?>>Bottom center</option>
        <option value="bottom_right" <?php if($options=='bottom_right'){echo "selected";}?>>Bottom right</option>
        <option value="top_left" <?php if($options=='top_left'){echo "selected";}?>>Top left</option>
        <option value="top_center" <?php if($options=='top_center'){echo "selected";}?>>Top center</option>
        <option value="top_right" <?php if($options=='top_right'){echo "selected";}?>>Top right</option>
      </select>
  <?php
  }

  public function glt_floating_widget_text_color_cb() {
    $option_name = 'glt_floating_widget_text_color';
    $new_value = '#ffffff';

    if (get_option($option_name) === false):
      update_option($option_name, $new_value);
    endif;

    $options = get_option(''.$option_name.''); ?>

    <input type="text" name="glt_floating_widget_text_color" id="glt_floating_widget_text_color" class="color-field" value="<?php echo esc_attr($options); ?>"/>
  <?php
  }

  public function glt_floating_widget_bg_color_cb() {
    $option_name = 'glt_floating_widget_bg_color';
    $new_value = '#f89406';

    if (get_option($option_name) === false):
      update_option($option_name, $new_value);
    endif;

    $options = get_option(''.$option_name.''); ?>

    <input type="text" name="glt_floating_widget_bg_color" id="glt_floating_widget_bg_color" class="color-field" value="<?php echo esc_attr($options); ?>"/>
  <?php
  }

  public function glt_language_switcher_width_cb() {

  $option_name = 'glt_language_switcher_width' ;
  $new_value = '';

  if ( get_option( $option_name ) === false ) {
    update_option( $option_name, $new_value );
  }

  $options = get_option (''.$option_name.''); ?>

  <select name="glt_language_switcher_width" id="glt_language_switcher_width" style="width:110px;">
    <option value="100%" <?php if($options=='100%'){echo "selected";}?>>100%</option>
    <option value="">-------</option>
    <option value="150px" <?php if($options=='150px'){echo "selected";}?>>150px</option>
    <option value="160px" <?php if($options=='160px'){echo "selected";}?>>160px</option>
    <option value="170px" <?php if($options=='170px'){echo "selected";}?>>170px</option>
    <option value="180px" <?php if($options=='180px'){echo "selected";}?>>180px</option>
    <option value="190px" <?php if($options=='190px'){echo "selected";}?>>190px</option>
    <option value="200px" <?php if($options=='200px'){echo "selected";}?>>200px</option>
    <option value="210px" <?php if($options=='210px'){echo "selected";}?>>210px</option>
    <option value="220px" <?php if($options=='220px'){echo "selected";}?>>220px</option>
    <option value="230px" <?php if($options=='230px'){echo "selected";}?>>230px</option>
    <option value="240px" <?php if($options=='240px'){echo "selected";}?>>240px</option>
    <option value="250px" <?php if($options=='250px'){echo "selected";}?>>250px</option>
    <option value="260px" <?php if($options=='260px'){echo "selected";}?>>260px</option>
    <option value="270px" <?php if($options=='270px'){echo "selected";}?>>270px</option>
    <option value="280px" <?php if($options=='280px'){echo "selected";}?>>280px</option>
    <option value="290px" <?php if($options=='290px'){echo "selected";}?>>290px</option>
    <option value="300px" <?php if($options=='300px'){echo "selected";}?>>300px</option>
  </select>
  <?php }

  public function glt_language_switcher_text_color_cb() {
    $option_name = 'glt_language_switcher_text_color';
    $new_value = '#32373c';

    if (get_option($option_name) === false):
      update_option($option_name, $new_value);
    endif;

    $options = get_option(''.$option_name.''); ?>

    <input type="text" name="glt_language_switcher_text_color" id="glt_language_switcher_text_color" class="color-field" value="<?php echo esc_attr($options); ?>"/>
  <?php
  }

  public function glt_language_switcher_bg_color_cb() {
    $option_name = 'glt_language_switcher_bg_color';
    $new_value = '';

    if (get_option($option_name) === false):
      update_option($option_name, $new_value);
    endif;

    $options = get_option(''.$option_name.''); ?>

    <input type="text" name="glt_language_switcher_bg_color" id="glt_language_switcher_bg_color" class="color-field" value="<?php echo esc_attr($options); ?>"/>
  <?php
  }

  public function googlelanguagetranslator_translatebox_cb() {

    $option_name = 'googlelanguagetranslator_translatebox' ;
    $new_value = 'yes';

    if(get_option($option_name) === false) {
        // The option does not exist, so we update it.
        update_option($option_name, $new_value);
    }

    $options = get_option (''.$option_name.''); ?>

    <select name="googlelanguagetranslator_translatebox" id="googlelanguagetranslator_translatebox" style="width:190px">
        <option value="yes" <?php if($options=='yes'){echo "selected";}?>>Show</option>
        <option value="no" <?php if($options=='no'){echo "selected";}?>>Hide</option>
    </select>
  <?php }

  public function googlelanguagetranslator_display_cb() {

    $option_name = 'googlelanguagetranslator_display' ;
    $new_value = 'Vertical';

      if ( get_option( $option_name ) === false ) {
          // The option does not exist, so we update it.
          update_option( $option_name, $new_value );
      }

      $options = get_option ($option_name); ?>

          <select name="googlelanguagetranslator_display" id="googlelanguagetranslator_display" style="width:170px;">
             <option value="Vertical" <?php if(get_option('googlelanguagetranslator_display') == 'Vertical'){echo "selected";}?>>Vertical</option>
             <option value="Horizontal" <?php if(get_option('googlelanguagetranslator_display') == 'Horizontal'){echo "selected";}?>>Horizontal</option>
          </select>
  <?php }

  public function googlelanguagetranslator_flags_alignment_cb() {

    $option_name = 'googlelanguagetranslator_flags_alignment' ;
    $new_value = 'flags_left';

      if ( get_option( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, 'flags_left' );
      }

      $options = get_option (''.$option_name.''); ?>

      <input type="radio" name="googlelanguagetranslator_flags_alignment" id="flags_left" value="flags_left" <?php if($options=='flags_left'){echo "checked";}?>/> <label for="flags_left">Align Left</label><br/>
      <input type="radio" name="googlelanguagetranslator_flags_alignment" id="flags_right" value="flags_right" <?php if($options=='flags_right'){echo "checked";}?>/> <label for="flags_right">Align Right</label>
  <?php }

  public function googlelanguagetranslator_flag_size_cb() {

    $option_name = 'googlelanguagetranslator_flag_size' ;
    $new_value = '18';

      if ( get_option( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
      }

      $options = get_option (''.$option_name.''); ?>

          <select name="googlelanguagetranslator_flag_size" id="googlelanguagetranslator_flag_size" style="width:110px;">
             <option value="16" <?php if($options=='16'){echo "selected";}?>>16px</option>
             <option value="18" <?php if($options=='18'){echo "selected";}?>>18px</option>
             <option value="20" <?php if($options=='20'){echo "selected";}?>>20px</option>
             <option value="22" <?php if($options=='22'){echo "selected";}?>>22px</option>
             <option value="24" <?php if($options=='24'){echo "selected";}?>>24px</option>
          </select>
  <?php }

  public function googlelanguagetranslator_flags_order_cb() {
    $option_name = 'googlelanguagetranslator_flags_order';
    $new_value = '';

    if ( get_option ( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
    }

    $options = get_option ( ''.$option_name.'' ); ?>

    <input type="hidden" id="order" name="googlelanguagetranslator_flags_order" value="<?php print_r(get_option('googlelanguagetranslator_flags_order')); ?>" />
   <?php
  }

  public function googlelanguagetranslator_english_flag_choice_cb() {
    $option_name = 'googlelanguagetranslator_english_flag_choice';
    $new_value = 'us_flag';

    if ( get_option ( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
    }

    $options = get_option ( ''.$option_name.'' ); ?>

    <select name="googlelanguagetranslator_english_flag_choice" id="googlelanguagetranslator_english_flag_choice">
      <option value="us_flag" <?php if($options=='us_flag'){echo "selected";}?>>U.S. Flag</option>
      <option value="uk_flag" <?php if ($options=='uk_flag'){echo "selected";}?>>U.K Flag</option>
      <option value="canadian_flag" <?php if ($options=='canadian_flag'){echo "selected";}?>>Canadian Flag</option>
    </select>
   <?php
  }

  public function googlelanguagetranslator_spanish_flag_choice_cb() {
    $option_name = 'googlelanguagetranslator_spanish_flag_choice';
    $new_value = 'spanish_flag';

    if ( get_option ( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
    }

    $options = get_option ( ''.$option_name.'' ); ?>

    <select name="googlelanguagetranslator_spanish_flag_choice" id="googlelanguagetranslator_spanish_flag_choice">
      <option value="spanish_flag" <?php if($options=='spanish_flag'){echo "selected";}?>>Spanish Flag</option>
      <option value="mexican_flag" <?php if ($options=='mexican_flag'){echo "selected";}?>>Mexican Flag</option>
    </select>
   <?php
  }

  public function googlelanguagetranslator_portuguese_flag_choice_cb() {
    $option_name = 'googlelanguagetranslator_portuguese_flag_choice';
    $new_value = 'portuguese_flag';

    if ( get_option ( $option_name ) === false ) {

      // The option does not exist, so we update it.
      update_option( $option_name, $new_value );
    }

    $options = get_option ( ''.$option_name.'' ); ?>

    <select name="googlelanguagetranslator_portuguese_flag_choice" id="googlelanguagetranslator_spanish_flag_choice">
      <option value="portuguese_flag" <?php if($options=='portuguese_flag'){echo "selected";}?>>Portuguese Flag</option>
      <option value="brazilian_flag" <?php if ($options=='brazilian_flag'){echo "selected";}?>>Brazilian Flag</option>
    </select>
   <?php
  }

  public function googlelanguagetranslator_seo_active_cb() {
    $option_name = 'googlelanguagetranslator_seo_active';
    $new_value   = 0;

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = absint( get_option( $option_name ) );
    ?>
    <input
        type="checkbox"
        name="googlelanguagetranslator_seo_active"
        id="googlelanguagetranslator_seo_active"
        value="1"
        <?php checked( 1, $options ); ?>
    />
    <?php
  }

  public function googlelanguagetranslator_url_structure_choice_cb() {
      $option_name = 'googlelanguagetranslator_url_structure' ;

      if ( get_option( $option_name ) === false ) {
          // The option does not exist, so we update it.
          update_option( $option_name, 'sub_domain' );
      }

      $options = get_option (''.$option_name.''); ?>

      <input type="radio" name="googlelanguagetranslator_url_structure" id="sub_domain" value="sub_domain" <?php if($options=='sub_domain'){echo "checked";}?>/> <label for="sub_domain">Sub-domain (http://<b>es</b>.example.com/)</label><br/><br/>
      <input type="radio" name="googlelanguagetranslator_url_structure" id="sub_directory" value="sub_directory" <?php if($options=='sub_directory'){echo "checked";}?>/> <label for="sub_directory">Sub-directory (http://example.com/<b>de</b>/)</label>
  <?php }

  public function googlelanguagetranslator_url_translation_active_cb() {
    $option_name = 'googlelanguagetranslator_url_translation_active';
    $new_value   = 0;

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = absint( get_option( $option_name ) );
    ?>
    <input
        type="checkbox"
        name="googlelanguagetranslator_url_translation_active"
        id="googlelanguagetranslator_url_translation_active"
        value="1"
        <?php checked( 1, $options ); ?>
    />
    <?php
  }

  public function googlelanguagetranslator_hreflang_tags_active_cb() {
    $option_name = 'googlelanguagetranslator_hreflang_tags_active';
    $new_value   = 0;

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = absint( get_option( $option_name ) );
    ?>
    <input
        type="checkbox"
        name="googlelanguagetranslator_hreflang_tags_active"
        id="googlelanguagetranslator_hreflang_tags_active"
        value="1"
        <?php checked( 1, $options ); ?>
    />
    <?php
  }

  public function googlelanguagetranslator_css_cb() {
    $option_name = 'googlelanguagetranslator_css';
    $new_value   = '';

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = get_option( $option_name );
    ?>
    <textarea
        style="width:100%;"
        rows="5"
        name="googlelanguagetranslator_css"
        id="googlelanguagetranslator_css"
    ><?php echo esc_textarea( $options ); ?></textarea>
    <?php
  }


  public function googlelanguagetranslator_exclude_translation_cb() {
    $option_name = 'googlelanguagetranslator_exclude_translation';
    $new_value   = '';

    if ( false === get_option( $option_name ) ) {
        update_option( $option_name, $new_value );
    }

    $options = sanitize_text_field( get_option( $option_name, '' ) );
    ?>
    <input
        type="text"
        name="<?php echo esc_attr( $option_name ); ?>"
        id="<?php echo esc_attr( $option_name ); ?>"
        value="<?php echo esc_attr( $options ); ?>"
    />
    <?php
  }

  public function page_layout_cb() {
    include( plugin_dir_path( __FILE__ ) . '/css/style.php'); add_thickbox(); ?>
      <div id="glt-settings" class="wrap">
        <div id="icon-options-general" class="icon32"></div>
      <h2><span class="notranslate">Google Language Translator</span></h2>
            <form action="<?php echo esc_url(admin_url( '/options.php')); ?>" method="post">
              <div class="metabox-holder has-right-sidebar" style="float:left; width:65%">
                <div class="postbox glt-main-settings" style="width: 100%">
                  <h3 class="notranslate">Main Settings</h3>
                    <?php settings_fields('google_language_translator'); ?>
                      <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">
                        <tr>
                          <td style="width:60%" class="notranslate">Plugin Status:</td>
                          <td class="notranslate"><?php $this->googlelanguagetranslator_active_cb(); ?></td>
                        </tr>

                        <tr class="notranslate">
                          <td>Choose the original language of your website</td>
                          <td><?php $this->googlelanguagetranslator_language_cb(); ?></td>
                        </tr>

                        <tr class="notranslate">
                          <td colspan="2">What languages will be active? (<a class="select-all-languages" href="#">Select All</a> | <a class="clear-all-languages" href="#">Clear</a>)</td>
                        </tr>

                        <tr class="notranslate languages">
                          <td colspan="2"><?php $this->language_display_settings_cb(); ?></td>
                        </tr>
                      </table>
                </div> <!-- .postbox -->

              <div class="postbox glt-seo-settings">
                <h3>SEO Settings (paid) <strong style="color:red">NEW!</strong></h3>
                  <div class="inside">
                    <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">
                      <tr class="notranslate">
                    <td class="advanced">Enable search engine indexing: &nbsp;<a href="#TB_inline?width=200&height=150&inlineId=search-engine-indexing-description" title="What is search engine indexing?" class="thickbox">Learn more</a><div id="search-engine-indexing-description" style="display:none"><p>When turned on search engines will crawl your translated pages and index them, so that your website's translated pages can appear in search engines results pages. This will increase your international traffic. Search engine indexing is an essential feature for multilingual SEO.<br><br><i>Please Note:</i> You must have <a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">GTranslate paid plan</a> to be able to use this option.</p></div></td>
                    <td class="advanced"><?php $this->googlelanguagetranslator_seo_active_cb(); ?></td>
                      </tr>

                      <tr class="notranslate">
                    <td class="advanced">URL Structure:</td>
                    <td class="advanced"><?php $this->googlelanguagetranslator_url_structure_choice_cb(); ?></td>
                      </tr>

                      <tr class="notranslate">
                    <td class="advanced">URL Translation: &nbsp;<a href="#TB_inline?width=200&height=150&inlineId=url-translation-description" title="What is URL translation?" class="thickbox">Learn more</a><div id="url-translation-description" style="display:none"><p>When turned on your URL slugs will be translated which will create additional keywords in other languages and increase your ranking on search engine results pages. For example http://example.com/<b>about-us</b> will become http://de.example.com/<b>uber-uns</b> for German version.<br><br><i>Please Note:</i> This feature will work only if you have GTranslate plan with URL translation option included.</p></div></td>
                    <td class="advanced"><?php $this->googlelanguagetranslator_url_translation_active_cb(); ?></td>
                      </tr>

                      <tr class="notranslate">
                    <td class="advanced">Add hreflang meta tags: &nbsp;<a href="#TB_inline?width=200&height=150&inlineId=hreflang-tags-description" title="What are hreflang tags?" class="thickbox">Learn more</a><div id="hreflang-tags-description" style="display:none"><p>Hreflang tags are a technical solution for sites that have similar content in multiple languages. The owner of a multilingual site wants search engines to send people to the content in their own language. Say a user is Dutch and the page that ranks is English, but there's also a Dutch version. You would want Google to show the Dutch page in the search results for that Dutch user. This is the kind of problem hreflang was designed to solve.</p></div></td>
                    <td class="advanced"><?php $this->googlelanguagetranslator_hreflang_tags_active_cb(); ?></td>
                      </tr>
                    </table>
                  </div> <!-- .inside -->
                </div> <!-- .postbox -->

                <div class="postbox glt-layout-settings" style="width: 100%">
                  <h3 class="notranslate">Language Switcher Settings</h3>
                  <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">

                  <tr class="notranslate">
                    <td class="choose_flags_intro">Language switcher width:</td>
                    <td class="choose_flags_intro"><?php $this->glt_language_switcher_width_cb(); ?></td>
                  </tr>

                  <tr class="notranslate">
                    <td class="choose_flags_intro">Language switcher text color:</td>
                    <td class="choose_flags_intro"><?php $this->glt_language_switcher_text_color_cb(); ?></td>
                  </tr>

                  <tr class="notranslate">
                    <td class="choose_flags_intro">Language switcher background color:</td>
                    <td class="choose_flags_intro"><?php $this->glt_language_switcher_bg_color_cb(); ?></td>
                  </tr>

                  <tr class="notranslate">
                    <td class="choose_flags_intro">Show flag images?<br/>(Display up to 104 flags above the language switcher)</td>
                    <td class="choose_flags_intro"><?php $this->googlelanguagetranslator_flags_cb(); ?></td>
                  </tr>

                    <tr class="notranslate">
                      <td>Show or hide the dropdown langauge switcher?</td>
                      <td><?php $this->googlelanguagetranslator_translatebox_cb(); ?></td>
                    </tr>

                    <tr class="notranslate">
                      <td>Layout option:</td>
                      <td><?php $this->googlelanguagetranslator_display_cb(); ?></td>
                    </tr>

                    <tr class="alignment notranslate">
                      <td class="flagdisplay">Align the translator left or right?</td>
                      <td class="flagdisplay"><?php $this->googlelanguagetranslator_flags_alignment_cb(); ?></td>
                    </tr>
                  </table>
                </div> <!-- .postbox -->

                <div class="postbox glt-floating-widget-settings" style="width: 100%">
                  <h3 class="notranslate">Floating Widget Settings</h3>
                  <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">
                    <tr class="floating_widget_show notranslate">
                      <td>Show floating translation widget?</td>
                      <td><?php $this->googlelanguagetranslator_floating_widget_cb(); ?></td>
                    </tr>

                    <tr class="floating-widget floating-widget-custom-text notranslate hidden">
                      <td>Custom text for the floating widget:</td>
                      <td><?php $this->googlelanguagetranslator_floating_widget_text_cb(); ?></td>
                    </tr>

                    <tr class="floating-widget floating-widget-text-translate notranslate hidden">
                      <td>Allow floating widget text to translate?:</td>
                      <td><?php $this->googlelanguagetranslator_floating_widget_text_allow_translation_cb(); ?></td>
                    </tr>

                    <tr class="floating-widget floating-widget-position notranslate hidden">
                      <td>Floating Widget Position:</td>
                      <td><?php $this->glt_floating_widget_position_cb(); ?></td>
                    </tr>

                    <tr class="floating-widget floating-widget-text-color notranslate hidden">
                      <td>Floating Widget Text Color:</td>
                      <td><?php $this->glt_floating_widget_text_color_cb(); ?></td>
                    </tr>

                    <tr class="floating-widget floating-widget-color notranslate hidden">
                      <td>Floating Widget Background Color</td>
                      <td><?php $this->glt_floating_widget_bg_color_cb(); ?></td>
                    </tr>
                  </table>
                </div> <!-- .postbox -->

                <div class="postbox glt-usage-settings" style="width: 100%">
                  <h3 class="notranslate">Usage</h3>
                  <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">
                    <tr class="notranslate">
                      <td>For usage in pages/posts/sidebar:</td>
                      <td><code>[google-translator]</code></td>
                    </tr>

                    <tr class="notranslate">
                      <td style="width:40%">For usage in header/footer/page templates:</td>
                      <td style="width:60%"><code>&lt;?php echo do_shortcode('[google-translator]'); ?&gt;</code></td>
                    </tr>

                    <tr class="notranslate">
                      <td colspan="2">Single language usage in menus/pages/posts</td>
                    </tr>

                    <tr class="notranslate">
                      <td colspan="2"><code>[glt language="Spanish" label="Espa&ntilde;ol" image="yes" text="yes" image_size="24"]</code></td>
                    </tr>

                    <tr class="notranslate">
                      <td colspan="2">
                        <a href="#TB_inline?width=200&height=450&inlineId=single-language-shortcode-description" title="How to place a single language in your Wordpress menu" class="thickbox">How to place a single language in your Wordpress menu</a>
            <div id="single-language-shortcode-description" style="display:none">
              <p>For menu usage, you need to create a new menu, or use an existing menu, by navigating to "Appearance > Menus".</p>
              <p>First you will need to enable "descriptions" for your menu items, which can be found in a tab labeled "Screen Options" in the upper-right area of the page.</p>
              <p>Once descriptions are enabled, follow these steps:<br/>
                            <ol>
                  <li>Create a new menu item using "Link" as the menu item type.</li>
                  <li>Use <code style="border:none">#</code> for the URL</li>
                  <li>Enter a navigation label of your choice. This label does not appear on your website - it is meant only to help you identify the menu item.</li>
                  <li>Place the following shortcode into the "description" field, and modify it to display the language and navigation label of your choice:</li>
                            </ol>
                          <p><code>[glt language="Spanish" label="Espa&ntilde;ol"]</code></p>
                        </div> <!-- .single-language-shortcode-description -->
                      </td>
                    </tr>
                  </table>
        </div> <!-- .postbox -->

        <?php
          if (isset($_POST['submit'])) {
            if (empty($_POST['submit']) && !check_admin_referer( 'glt-save-settings', 'glt-save-settings-nonce' )) {
              wp_die();
            }
          }
          wp_nonce_field('glt-save-settings, glt-save-settings-nonce', false);
              submit_button();
        ?>

        <p><a target="_blank" href="https://wordpress.org/support/plugin/google-language-translator/reviews/"><?php esc_html_e('Love Google Language Translator? Give us 5 stars on WordPress.org :)', 'google-language-translator'); ?></a></p>

        </div> <!-- .metbox-holder -->

        <div class="metabox-holder" style="float:right; clear:right; width:33%">
          <div class="postbox glt-preview-settings">
            <h3 class="notranslate">Preview</h3>
                      <table style="width:100%">
                <tr>
                          <td style="box-sizing:border-box; -webkit-box-sizing:border-box; -moz-box-sizing:border-box; padding:15px 15px; margin:0px"><span class="notranslate"> Drag &amp; drop flags to change their position.<br/><br/>(Note: flag order resets when flags are added/removed)</span><br/><br/><?php echo do_shortcode('[google-translator]'); ?><p class="hello"><span class="notranslate">Translated text:</span> &nbsp; <span>Hello</span></p>
                          </td>
                        </tr>
                      </table>
          </div> <!-- .postbox -->
            </div> <!-- .metabox-holder -->

                <div class="metabox-holder box-right notranslate" style="float: right; width: 33%; clear:right">
                  <div class="postbox glt-flag-settings">
                    <h3>Flag Settings</h3>
                      <div class="inside">
                        <table style="border-collapse:separate" width="100%" border="0" cellspacing="8" cellpadding="0" class="form-table">
                          <tr class="notranslate">
                        <td class="advanced">Select flag size:</td>
                        <td class="advanced"><?php $this->googlelanguagetranslator_flag_size_cb(); ?></td>
                          </tr>

                          <tr class="notranslate">
                        <td class="advanced">Flag for English:</td>
                        <td class="advanced"><?php $this->googlelanguagetranslator_english_flag_choice_cb(); ?></td>
                          </tr>

                          <tr class="notranslate">
                        <td class="advanced">Flag for Spanish:</td>
                        <td class="advanced"><?php $this->googlelanguagetranslator_spanish_flag_choice_cb(); ?></td>
                          </tr>

                          <tr class="notranslate">
                        <td class="advanced">Flag for Portuguese:</td>
                        <td class="advanced"><?php $this->googlelanguagetranslator_portuguese_flag_choice_cb(); ?></td>
                          </tr>
                        </table>
                      </div> <!-- .inside -->
                    </div> <!-- .postbox -->
                  </div> <!-- .metabox-holder -->

            <div class="metabox-holder box-right notranslate" style="float: right; width: 33%;">
              <div class="postbox glt-gtranslate-ad">
                <h3>Enable SEO features with GTranslate</h3>
                  <div class="inside">
                    <a class="wp-studio-logo" href="https://gtranslate.io/?xyz=3167#pricing" target="_blank"><img style="width:177px;" src="<?php echo esc_url(plugins_url( 'images/gt_logo.svg' , __FILE__ )); ?>"></a><br />
                      <ul id="features" style="margin-left:15px">
                        <li style="list-style:square outside"><?php esc_html_e('Search engine indexing', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Search engine friendly (SEF) URLs', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Human level neural translations', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Edit translations manually', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><a href="https://gtranslate.io/website-translation-quote" title="Website Translation Price Calculator" target="_blank"><?php esc_html_e('Automatic translation post-editing service and professional translations', 'google-language-translator'); ?></a></li>
                        <li style="list-style:square outside"><?php esc_html_e('Meta data translation (keywords, page description, etc...)', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('URL/slug translation', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Language hosting (custom domain like example.fr, example.es)', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Seamless updates', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Increased international traffic and AdSense revenue', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Works in China', 'google-language-translator'); ?></li>
                        <li style="list-style:square outside"><?php esc_html_e('Priority Live Chat support', 'google-language-translator'); ?></li>
                      </ul>

                      <p>
                          <?php
                          echo wp_kses_post(
                              sprintf(
                                  /* translators: %s: starting monthly price. */
                                  __( 'Prices starting from <b>%s/month</b>!', 'google-language-translator' ),
                                  '$12'
                               )
                          );
                          ?>
                      </p>

                      <a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank" class="button-primary"><?php esc_html_e('Try Now (15 days free)', 'google-language-translator'); ?></a> <a href="https://gtranslate.io/?xyz=3167#faq" target="_blank" class="button-primary"><?php esc_html_e('FAQ', 'google-language-translator'); ?></a> <a href="https://gtranslate.io/?xyz=3167#contact" target="_blank" class="button-primary"><?php esc_html_e('Live Chat', 'google-language-translator'); ?></a>
                  </div> <!-- .inside -->
              </div> <!-- .postbox -->
            </div> <!-- .metabox-holder -->


              <div class="metabox-holder box-right notranslate" style="float: right; width: 33%;">
                    <div class="postbox glt-css-settings">
                      <h3>Add CSS Styles</h3>
            <div class="inside">
              <p>You can apply any necessary CSS styles below:</p>
              <?php $this->googlelanguagetranslator_css_cb(); ?>
                        </div> <!-- .inside -->
                    </div> <!-- .postbox -->
                  </div> <!-- .metabox-holder -->
              <?php $this->googlelanguagetranslator_flags_order_cb(); ?>
        </form>
      </div> <!-- .wrap -->

      <?php
      $default_language = get_option('googlelanguagetranslator_language');
      $glt_url_structure = get_option('googlelanguagetranslator_url_structure');
      $glt_seo_active = get_option('googlelanguagetranslator_seo_active');

      $pro_version = $enterprise_version = null;
      if($glt_seo_active == '1' and $glt_url_structure == 'sub_domain')
         $pro_version = '1';
      if($glt_seo_active == '1' and $glt_url_structure == 'sub_directory')
         $enterprise_version = '1';
      ?>
      <script>window.intercomSettings = {app_id: "r70azrgx", 'platform': 'wordpress-glt', 'translate_from': '<?php echo esc_js($default_language); ?>', 'is_sub_directory': <?php echo esc_js(empty($pro_version) ? '0' : '1'); ?>, 'is_sub_domain': <?php echo esc_js(empty($enterprise_version) ? '0' : '1'); ?>};(function(){var w=window;var ic=w.Intercom;if(typeof ic==="function"){ic('reattach_activator');ic('update',intercomSettings);}else{var d=document;var i=function(){i.c(arguments)};i.q=[];i.c=function(args){i.q.push(args)};w.Intercom=i;function l(){var s=d.createElement('script');s.type='text/javascript';s.async=true;s.src='https://widget.intercom.io/widget/r70azrgx';var x=d.getElementsByTagName('script')[0];x.parentNode.insertBefore(s,x);}if(w.attachEvent){w.attachEvent('onload',l);}else{w.addEventListener('load',l,false);}}})()</script>
<?php
  }
}

class GLT_Notices {
    protected $prefix = 'glt';
    public $notice_spam = 0;
    public $notice_spam_max = 3;

    // Basic actions to run
    public function __construct() {
        // Runs the admin notice ignore function incase a dismiss button has been clicked
        add_action('admin_init', array($this, 'admin_notice_ignore'));
        // Runs the admin notice temp ignore function incase a temp dismiss link has been clicked
        add_action('admin_init', array($this, 'admin_notice_temp_ignore'));

        // Adding notices
        add_action('admin_notices', array($this, 'glt_admin_notices'));
    }

    // Checks to ensure notices aren't disabled and the user has the correct permissions.
    public function glt_admin_notice() {

        $gt_settings = get_option($this->prefix . '_admin_notice');
        if (!isset($gt_settings['disable_admin_notices']) || (isset($gt_settings['disable_admin_notices']) && $gt_settings['disable_admin_notices'] == 0)) {
            if (current_user_can('manage_options')) {
                return true;
            }
        }
        return false;
    }

    // Primary notice function that can be called from an outside function sending necessary variables
    public function admin_notice($admin_notices) {

        // Check options
        if (!$this->glt_admin_notice()) {
            return false;
        }

        foreach ($admin_notices as $slug => $admin_notice) {
            // Call for spam protection

            if ($this->anti_notice_spam()) {
                return false;
            }

            // Check for proper page to display on
            if (isset( $admin_notices[$slug]['pages']) and is_array( $admin_notices[$slug]['pages'])) {

                if (!$this->admin_notice_pages($admin_notices[$slug]['pages'])) {
                    return false;
                }

            }

            // Check for required fields
            if (!$this->required_fields($admin_notices[$slug])) {

                // Get the current date then set start date to either passed value or current date value and add interval
                $current_date = current_time("n/j/Y");
                $start = (isset($admin_notices[$slug]['start']) ? $admin_notices[$slug]['start'] : $current_date);
                $start = gmdate("n/j/Y", strtotime($start));
                $end = ( isset( $admin_notices[ $slug ]['end'] ) ? $admin_notices[ $slug ]['end'] : $start );
                $end = gmdate( "n/j/Y", strtotime( $end ) );
                $date_array = explode('/', $start);
                $interval = (isset($admin_notices[$slug]['int']) ? $admin_notices[$slug]['int'] : 0);
                $date_array[1] += $interval;
                $start = gmdate("n/j/Y", mktime(0, 0, 0, $date_array[0], $date_array[1], $date_array[2]));
                // This is the main notices storage option
                $admin_notices_option = get_option($this->prefix . '_admin_notice', array());
                // Check if the message is already stored and if so just grab the key otherwise store the message and its associated date information
                if (!array_key_exists( $slug, $admin_notices_option)) {
                    $admin_notices_option[$slug]['start'] = $start;
                    $admin_notices_option[$slug]['int'] = $interval;
                    update_option($this->prefix . '_admin_notice', $admin_notices_option);
                }

                // Sanity check to ensure we have accurate information
                // New date information will not overwrite old date information
                $admin_display_check = (isset($admin_notices_option[$slug]['dismissed']) ? $admin_notices_option[$slug]['dismissed'] : 0);
                $admin_display_start = (isset($admin_notices_option[$slug]['start']) ? $admin_notices_option[$slug]['start'] : $start);
                $admin_display_interval = (isset($admin_notices_option[$slug]['int']) ? $admin_notices_option[$slug]['int'] : $interval);
                $admin_display_msg = (isset($admin_notices[$slug]['msg']) ? $admin_notices[$slug]['msg'] : '');
                $admin_display_title = (isset($admin_notices[$slug]['title']) ? $admin_notices[$slug]['title'] : '');
                $admin_display_link = (isset($admin_notices[$slug]['link']) ? $admin_notices[$slug]['link'] : '');
                $admin_display_dismissible= (isset($admin_notices[$slug]['dismissible']) ? $admin_notices[$slug]['dismissible'] : true);
                $output_css = false;

                // Ensure the notice hasn't been hidden and that the current date is after the start date
                if ($admin_display_check == 0 and strtotime($admin_display_start) <= strtotime($current_date)) {
                    // Get remaining query string
                    $query_str = wp_nonce_url(add_query_arg($this->prefix . '_admin_notice_ignore', $slug), 'glt-dismiss-notice');

                    // Admin notice display output
                    echo '<div class="update-nag glt-admin-notice">';
                    echo '<div class="glt-notice-logo"></div>';
                    echo ' <p class="glt-notice-title">';
                    echo wp_kses_post($admin_display_title);
                    echo ' </p>';
                    echo ' <p class="glt-notice-body">';
                    echo wp_kses_post($admin_display_msg);
                    echo ' </p>';
                    echo '<ul class="glt-notice-body glt-red">
                          ' . wp_kses_post($admin_display_link) . '
                        </ul>';
                    if($admin_display_dismissible)
                        echo '<a href="' . esc_url($query_str) . '" class="dashicons dashicons-dismiss"></a>';
                    echo '</div>';

                    $this->notice_spam += 1;
                    $output_css = true;
                }

                if ($output_css) {
                    wp_enqueue_style($this->prefix . '-admin-notices', plugins_url(plugin_basename(dirname(__FILE__))) . '/css/glt-notices.css', array());
                }
            }

        }
    }

    // Spam protection check
    public function anti_notice_spam() {
        if ($this->notice_spam >= $this->notice_spam_max) {
            return true;
        }
        return false;
    }

    // Ignore function that gets ran at admin init to ensure any messages that were dismissed get marked
    public function admin_notice_ignore() {
        // If user clicks to ignore the notice, update the option to not show it again
        if(isset($_GET[$this->prefix . '_admin_notice_ignore']) and $this->can_dismiss_notice($_GET[$this->prefix . '_admin_notice_ignore'])) {
            $admin_notices_option = get_option($this->prefix . '_admin_notice', array());

            $key = $_GET[$this->prefix . '_admin_notice_ignore'];
            if(!preg_match('/^[a-z_0-9]+$/i', $key))
                return;

            $admin_notices_option[$key]['dismissed'] = 1;
            update_option($this->prefix . '_admin_notice', $admin_notices_option);
            $query_str = remove_query_arg(array($this->prefix . '_admin_notice_ignore', '_wpnonce'));
            wp_safe_redirect($query_str);
            exit;
        }
    }

    // Temp Ignore function that gets ran at admin init to ensure any messages that were temp dismissed get their start date changed
    public function admin_notice_temp_ignore() {
        // If user clicks to temp ignore the notice, update the option to change the start date - default interval of 14 days
        if(isset($_GET[$this->prefix . '_admin_notice_temp_ignore']) and $this->can_dismiss_notice($_GET[$this->prefix . '_admin_notice_temp_ignore'])) {
            $admin_notices_option = get_option($this->prefix . '_admin_notice', array());
            $current_date = current_time("n/j/Y");
            $date_array   = explode('/', $current_date);
            $interval     = (isset($_GET['gt_int']) ? intval($_GET['gt_int']) : 14);
            $date_array[1] += $interval;
            $new_start = gmdate("n/j/Y", mktime(0, 0, 0, $date_array[0], $date_array[1], $date_array[2]));

            $key = $_GET[$this->prefix . '_admin_notice_temp_ignore'];
            if(!preg_match('/^[a-z_0-9]+$/i', $key))
                return;

            $admin_notices_option[$key]['start'] = $new_start;
            $admin_notices_option[$key]['dismissed'] = 0;
            update_option($this->prefix . '_admin_notice', $admin_notices_option);
            $query_str = remove_query_arg(array($this->prefix . '_admin_notice_temp_ignore', 'gt_int', '_wpnonce'));
            wp_safe_redirect($query_str);
            exit;
        }
    }

    public function admin_notice_pages($pages) {
        foreach ($pages as $key => $page) {
            if (is_array($page)) {
                if (isset($_GET['page']) and $_GET['page'] == $page[0] and isset($_GET['tab']) and $_GET['tab'] == $page[1]) {
                    return true;
                }
            } else {
                if ($page == 'all') {
                    return true;
                }
                if (get_current_screen()->id === $page) {
                    return true;
                }

                if (isset($_GET['page']) and $_GET['page'] == $page) {
                    return true;
                }
            }
        }

        return false;
    }

    // Required fields check
    public function required_fields( $fields ) {
        if (!isset( $fields['msg']) or (isset($fields['msg']) and empty($fields['msg']))) {
            return true;
        }
        if (!isset( $fields['title']) or (isset($fields['title']) and empty($fields['title']))) {
            return true;
        }
        return false;
    }

    // Special parameters function that is to be used in any extension of this class
    public function special_parameters($admin_notices) {
        // Intentionally left blank
    }

    private function can_dismiss_notice($key) {
        if(!current_user_can('manage_options') or !is_string($key) or !in_array($key, array('two_week_review', 'upgrade_tips', 'glt_announcement'), true) or !isset($_GET['_wpnonce']) or !is_string($_GET['_wpnonce']))
            return false;

        return (bool) wp_verify_nonce(sanitize_text_field(wp_unslash($_GET['_wpnonce'])), 'glt-dismiss-notice');
    }

    public function glt_admin_notices() {

        $deactivate_plugins= array('WP Translator' => 'wptranslator/WPTranslator.php', 'TranslatePress' => 'translatepress-multilingual/index.php', 'Google Website Translator' => 'google-website-translator/google-website-translator.php', 'Weglot' => 'weglot/weglot.php', 'TransPosh' => 'transposh-translation-filter-for-wordpress/transposh.php', 'Advanced Google Translate' => 'advanced-google-translate/advanced-google-translate.php', 'My WP Translate' => 'my-wp-translate/my-wp-translate.php', 'WPML Multilingual CMS' => 'sitepress-multilingual-cms/sitepress.php');
        foreach($deactivate_plugins as $name => $plugin_file) {
            if(is_plugin_active($plugin_file)) {
                $deactivate_link = wp_nonce_url('plugins.php?action=deactivate&amp;plugin='.urlencode($plugin_file ).'&amp;plugin_status=all&amp;paged=1&amp;s=', 'deactivate-plugin_' . $plugin_file);
                $notices['deactivate_plugin_'.strtolower(str_replace(' ', '', $name))] = array(
                    /* translators: %s: plugin name. */
                    'title' => sprintf(__('Please deactivate %s plugin', 'google-language-translator'), $name),

                    /* translators: %s: plugin name. */
                    'msg' => sprintf(__('%s plugin causes conflicts with Google Language Translator.', 'google-language-translator'), $name),

                    /* translators: %s: plugin name. */
                    'link' => '<li><span class="dashicons dashicons-dismiss"></span><a href="'.$deactivate_link.'">' . sprintf(__('Deactivate %s plugin', 'google-language-translator'), $name) . '</a></li>',
                    'dismissible' => false,
                    'int' => 0
                );
            }
        }

        // check if translation debug is on and add a notice
        include dirname(__FILE__) . '/url_addon/config.php';
        if($debug) {
            $edit_file_link = admin_url('plugin-editor.php?file=google-language-translator%2Furl_addon%2Fconfig.php&plugin=google-language-translator%2Fgoogle-language-translator.php');
            $view_debug_link = admin_url('plugin-editor.php?file=google-language-translator%2Furl_addon%2Fdebug.txt&plugin=google-language-translator%2Fgoogle-language-translator.php');
            $notices['glt_debug_notice'] = array(
                'title' => __('Translation debug mode is ON.', 'google-language-translator'),
                'msg' => __('Please note that sensitive information can be written into google-language-translator/url_addon/debug.txt file, which can be accessed publicly. It is your responsibility to deny public access to it and clean debug information after you are done.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-edit"></span><a href="'.$edit_file_link.'">' . __('Edit config.php', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-visibility"></span><a href="'.$view_debug_link.'">' . __('View debug.txt', 'google-language-translator') . '</a></li>',
                'dismissible' => false,
                'int' => 0
            );
        }

        $glt_announcement_ignore = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_ignore' => 'glt_announcement')), 'glt-dismiss-notice'));
        $glt_announcement_temp = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_temp_ignore' => 'glt_announcement', 'gt_int' => 2)), 'glt-dismiss-notice'));

        $notices['glt_announcement'] = array(
            'title' => __('Announcement - Google Language Translator', 'google-language-translator'),
            'msg' => __("<p><b>Google Language Translator</b> plugin is now a part of <b>GTranslate</b> family!</p> <p>GTranslate is a leader in website translation technology. You can continue using this plugin and enjoy <b>new SEO features</b> and free <b>Live chat support</b> brought to you by GTranslate.</p>", 'google-language-translator'),
            'link' => '<li><span class="dashicons dashicons-megaphone"></span><a href="https://gtranslate.io/blog/google-language-translator-becomes-part-of-gtranslate-family" target="_blank">' . __('Read More', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167" target="_blank">' . __('Visit GTranslate', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-admin-settings"></span><a href="' . admin_url('options-general.php?page=google_language_translator') . '">' . __('Open Settings Page', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $glt_announcement_temp . '">' . __('Remind me later', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $glt_announcement_ignore . '">' . __('Dismiss', 'google-language-translator') . '</a></li>',
            'later_link' => $glt_announcement_temp,
            'int' => 0
        );

        $two_week_review_ignore = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_ignore' => 'two_week_review')), 'glt-dismiss-notice'));
        $two_week_review_temp = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_temp_ignore' => 'two_week_review', 'gt_int' => 6)), 'glt-dismiss-notice'));

        $notices['two_week_review'] = array(
            'title' => __('Please Leave a Review', 'google-language-translator'),
            'msg' => __("We hope you have enjoyed using Google Language Translator! Would you mind taking a few minutes to write a review on WordPress.org? <br>Just writing a simple <b>'thank you'</b> will make us happy!", 'google-language-translator'),
            'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://wordpress.org/support/plugin/google-language-translator/reviews/" target="_blank">' . __('Sure! I would love to!', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-smiley"></span><a href="' . $two_week_review_ignore . '">' . __('I have already left a review', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $two_week_review_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                      '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $two_week_review_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
            'later_link' => $two_week_review_temp,
            'int' => 5
        );

        $upgrade_tips_ignore = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_ignore' => 'upgrade_tips')), 'glt-dismiss-notice'));
        $upgrade_tips_temp = esc_url(wp_nonce_url(add_query_arg(array($this->prefix . '_admin_notice_temp_ignore' => 'upgrade_tips', 'gt_int' => 7)), 'glt-dismiss-notice'));

        if(get_option('googlelanguagetranslator_seo_active') != '1') {
            $notices['upgrade_tips'][] = array(
                'title' => __('Did you know?', 'google-language-translator'),
                'msg' => __('You can have <b>neural machine translations</b> which are human level with GTranslate paid version.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">' . __('Learn more', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $upgrade_tips_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $upgrade_tips_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
                'later_link' => $upgrade_tips_temp,
                'int' => 2
            );

            $notices['upgrade_tips'][] = array(
                'title' => __('Did you know?', 'google-language-translator'),
                'msg' => __('You can <b>increase</b> your international <b>traffic</b> with GTranslate paid version.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">' . __('Learn more', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $upgrade_tips_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $upgrade_tips_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
                'later_link' => $upgrade_tips_temp,
                'int' => 2
            );

            $notices['upgrade_tips'][] = array(
                'title' => __('Did you know?', 'google-language-translator'),
                'msg' => __('You can have your <b>translated pages indexed</b> in search engines with GTranslate paid version.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">' . __('Learn more', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $upgrade_tips_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $upgrade_tips_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
                'later_link' => $upgrade_tips_temp,
                'int' => 2
            );

            $notices['upgrade_tips'][] = array(
                'title' => __('Did you know?', 'google-language-translator'),
                'msg' => __('You can <b>increase</b> your <b>AdSense revenue</b> with GTranslate paid version.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">' . __('Learn more', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $upgrade_tips_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $upgrade_tips_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
                'later_link' => $upgrade_tips_temp,
                'int' => 2
            );

            $notices['upgrade_tips'][] = array(
                'title' => __('Did you know?', 'google-language-translator'),
                'msg' => __('You can <b>edit translations</b> with GTranslate paid version.', 'google-language-translator'),
                'link' => '<li><span class="dashicons dashicons-external"></span><a href="https://gtranslate.io/?xyz=3167#pricing" target="_blank">' . __('Learn more', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-calendar-alt"></span><a href="' . $upgrade_tips_temp . '">' . __('Maybe later', 'google-language-translator') . '</a></li>' .
                          '<li><span class="dashicons dashicons-dismiss"></span><a href="' . $upgrade_tips_ignore . '">' . __('Never show again', 'google-language-translator') . '</a></li>',
                'later_link' => $upgrade_tips_temp,
                'int' => 2
            );

            shuffle($notices['upgrade_tips']);
            $notices['upgrade_tips'] = $notices['upgrade_tips'][0];
        }

        $this->admin_notice($notices);
    }
}

if(is_admin()) {
    global $pagenow;

    if(!defined('DOING_AJAX') or !DOING_AJAX)
        new GLT_Notices();
}

global $glt_url_structure, $glt_seo_active;

$glt_url_structure = get_option('googlelanguagetranslator_url_structure');
$glt_seo_active = get_option('googlelanguagetranslator_seo_active');

if($glt_seo_active == '1' and $glt_url_structure == 'sub_directory') { // gtranslate redirect rules with PHP (for environments with no .htaccess support (pantheon, flywheel, etc.), usually .htaccess rules override this)

    @list($request_uri, $query_params) = explode('?', $_SERVER['REQUEST_URI']);

    if(preg_match('/^\/(af|sq|am|ar|hy|az|eu|be|bn|bs|bg|ca|ceb|ny|zh-CN|zh-TW|co|hr|cs|da|nl|en|eo|et|tl|fi|fr|fy|gl|ka|de|el|gu|ht|ha|haw|iw|hi|hmn|hu|is|ig|id|ga|it|ja|jw|kn|kk|km|ko|ku|ky|lo|la|lv|lt|lb|mk|mg|ms|ml|mt|mi|mr|mn|my|ne|no|ps|fa|pl|pt|pa|ro|ru|sm|gd|sr|st|sn|sd|si|sk|sl|so|es|su|sw|sv|tg|ta|te|th|tr|uk|ur|uz|vi|cy|xh|yi|yo|zu)\/(af|sq|am|ar|hy|az|eu|be|bn|bs|bg|ca|ceb|ny|zh-CN|zh-TW|co|hr|cs|da|nl|en|eo|et|tl|fi|fr|fy|gl|ka|de|el|gu|ht|ha|haw|iw|hi|hmn|hu|is|ig|id|ga|it|ja|jw|kn|kk|km|ko|ku|ky|lo|la|lv|lt|lb|mk|mg|ms|ml|mt|mi|mr|mn|my|ne|no|ps|fa|pl|pt|pa|ro|ru|sm|gd|sr|st|sn|sd|si|sk|sl|so|es|su|sw|sv|tg|ta|te|th|tr|uk|ur|uz|vi|cy|xh|yi|yo|zu)\/(.*)$/', $request_uri, $matches)) {
        header('Location: ' . '/' . $matches[1] . '/' . $matches[3] . (empty($query_params) ? '' : '?'.$query_params), true, 301);
        exit;
    } // #1 redirect double language codes /es/en/...

    if(preg_match('/^\/(af|sq|am|ar|hy|az|eu|be|bn|bs|bg|ca|ceb|ny|zh-CN|zh-TW|co|hr|cs|da|nl|en|eo|et|tl|fi|fr|fy|gl|ka|de|el|gu|ht|ha|haw|iw|hi|hmn|hu|is|ig|id|ga|it|ja|jw|kn|kk|km|ko|ku|ky|lo|la|lv|lt|lb|mk|mg|ms|ml|mt|mi|mr|mn|my|ne|no|ps|fa|pl|pt|pa|ro|ru|sm|gd|sr|st|sn|sd|si|sk|sl|so|es|su|sw|sv|tg|ta|te|th|tr|uk|ur|uz|vi|cy|xh|yi|yo|zu)$/', $request_uri)) {
        header('Location: ' . $request_uri . '/' . (empty($query_params) ? '' : '?'.$query_params), true, 301);
        exit;
    } // #2 add trailing slash

    $get_language_choices = get_option ('language_display_settings');
    $items = array();
    foreach($get_language_choices as $key => $value) {
        if($value == 1)
            $items[] = $key;
    }
    $allowed_languages = implode('|', $items); // ex: en|ru|it|de

    if(preg_match('/^\/('.$allowed_languages.')\/(.*)/', $request_uri, $matches)) {
        $_GET['glang'] = $matches[1];
        $_GET['gurl'] = rawurldecode($matches[2]);

        require_once dirname(__FILE__) . '/url_addon/gtranslate.php';
        exit;
    } // #3 proxy translation
}

if($glt_seo_active == '1' and ($glt_url_structure == 'sub_directory' or $glt_url_structure == 'sub_domain')) {
    add_action('wp_head', 'glt_request_uri_var');
    if(isset($_GET['page']) and $_GET['page'] == 'google_language_translator')
        add_action('admin_head', 'glt_request_uri_var');

    function glt_request_uri_var() {
        global $glt_url_structure;

        $request_uri = isset( $_SERVER['REQUEST_URI'] ) ? sanitize_url( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '';
        $url_structure = sanitize_key( $glt_url_structure );
        $default_lang  = sanitize_text_field( (string) get_option( 'googlelanguagetranslator_language', '' ) );
        ?>
        <script>
        var glt_request_uri = <?php echo wp_json_encode($request_uri); ?>;
        var glt_url_structure = <?php echo wp_json_encode($url_structure); ?>;
        var glt_default_lang = <?php echo wp_json_encode($default_lang); ?>;
        </script>
        <?php
    }

    if(get_option('googlelanguagetranslator_url_translation_active') == '1') {
        add_action('wp_head', 'glt_url_translation_meta', 1);
        function glt_url_translation_meta() {
            echo '<meta name="uri-translation" content="on" />';
        }
    }

    if(get_option('googlelanguagetranslator_hreflang_tags_active') == '1') {
        add_action('wp_head', 'glt_add_hreflang_tags', 1);

        function glt_add_hreflang_tags() {
            global $glt_url_structure;

            $default_language = get_option('googlelanguagetranslator_language');
            $enabled_languages = array();
            $get_language_choices = get_option ('language_display_settings');
            foreach($get_language_choices as $key => $value) {
                if($value == 1)
                    $enabled_languages[] = $key;
            }

            //$current_url = wp_get_canonical_url();
            $current_url = network_home_url(add_query_arg(null, null));

            if($current_url !== false) {
                // adding default language
                if($default_language === 'iw')
                    echo '<link rel="alternate" hreflang="he" href="'.esc_url($current_url).'" />'."\n";
                elseif($default_language === 'jw')
                    echo '<link rel="alternate" hreflang="jv" href="'.esc_url($current_url).'" />'."\n";
                else
                    echo '<link rel="alternate" hreflang="'.esc_attr($default_language).'" href="'.esc_url($current_url).'" />'."\n";

                // adding enabled languages
                foreach($enabled_languages as $lang) {
                    $href = '';
                    $domain = str_replace('www.', '', $_SERVER['HTTP_HOST']);

                    if($glt_url_structure == 'sub_domain')
                        $href = str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $lang . '.' . $domain, $current_url);
                    elseif($glt_url_structure == 'sub_directory')
                        $href = str_ireplace('://' . $_SERVER['HTTP_HOST'], '://' . $_SERVER['HTTP_HOST'] . '/' . $lang, $current_url);

                    if(!empty($href) and $lang != $default_language) {
                        if($lang === 'iw')
                            echo '<link rel="alternate" hreflang="he" href="'.esc_url($href).'" />'."\n";
                        elseif($lang === 'jw')
                            echo '<link rel="alternate" hreflang="jv" href="'.esc_url($href).'" />'."\n";
                        else
                            echo '<link rel="alternate" hreflang="'.esc_attr($lang).'" href="'.esc_url($href).'" />'."\n";
                    }
                }
            }
        }
    }
}


// translate WP REST API posts and categories data in JSON response
if($glt_seo_active == '1') {
    function glt_rest_post($response, $post, $request) {
        if(isset($response->data['content']) and is_array($response->data['content']))
            $response->data['content']['gt_translate_keys'] = array(array('key' => 'rendered', 'format' => 'html'));

        if(isset($response->data['excerpt']) and is_array($response->data['excerpt']))
            $response->data['excerpt']['gt_translate_keys'] = array(array('key' => 'rendered', 'format' => 'html'));

        if(isset($response->data['title']) and is_array($response->data['title']))
            $response->data['title']['gt_translate_keys'] = array(array('key' => 'rendered', 'format' => 'text'));

        if(isset($response->data['link']))
            $response->data['gt_translate_keys'] = array(array('key' => 'link', 'format' => 'url'));

        // more fields can be added here

        return $response;
    }

    function glt_rest_category($response, $category, $request) {
        if(isset($response->data['description']))
            $response->data['gt_translate_keys'][] = array('key' => 'description', 'format' => 'html');

        if(isset($response->data['name']))
            $response->data['gt_translate_keys'][] = array('key' => 'name', 'format' => 'text');

        if(isset($response->data['link']))
            $response->data['gt_translate_keys'][] = array('key' => 'link', 'format' => 'url');

        // more fields can be added here

        return $response;
    }

    add_filter('rest_prepare_post', 'glt_rest_post', 10, 3);
    add_filter('rest_prepare_category', 'glt_rest_category', 10, 3);
}

// convert wp_localize_script format into JSON + JS parser
if($glt_seo_active == '1') {
    // filter for woocommerce script params
    function glt_filter_woocommerce_scripts_data($data, $handle) {
        switch($handle) {
            case 'wc-address-i18n': {
                $data['gt_translate_keys'] = array(
                    array('key' => 'locale', 'format' => 'json'),
                    'i18n_required_text',
                    'i18n_optional_text',
                );

                $locale = json_decode($data['locale']);

                if(isset($locale->default->address_1))
                    $locale->default->address_1->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->address_2))
                    $locale->default->address_2->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->city))
                    $locale->default->city->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->postcode))
                    $locale->default->postcode->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->state))
                    $locale->default->state->gt_translate_keys = array('label', 'placeholder');

                if(isset($locale->default->shipping->address_1))
                    $locale->default->shipping->address_1->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->shipping->address_2))
                    $locale->default->shipping->address_2->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->shipping->city))
                    $locale->default->shipping->city->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->shipping->postcode))
                    $locale->default->shipping->postcode->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->shipping->state))
                    $locale->default->shipping->state->gt_translate_keys = array('label', 'placeholder');

                if(isset($locale->default->billing->address_1))
                    $locale->default->billing->address_1->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->billing->address_2))
                    $locale->default->billing->address_2->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->billing->city))
                    $locale->default->billing->city->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->billing->postcode))
                    $locale->default->billing->postcode->gt_translate_keys = array('label', 'placeholder');
                if(isset($locale->default->billing->state))
                    $locale->default->billing->state->gt_translate_keys = array('label', 'placeholder');

                $data['locale'] = json_encode($locale);
            } break;

            case 'wc-checkout': {
                $data['gt_translate_keys'] = array('i18n_checkout_error');
            } break;

            case 'wc-country-select': {
                $data['gt_translate_keys'] = array('i18n_ajax_error', 'i18n_input_too_long_1', 'i18n_input_too_long_n', 'i18n_input_too_short_1', 'i18n_input_too_short_n', 'i18n_load_more', 'i18n_no_matches', 'i18n_searching', 'i18n_select_state_text', 'i18n_selection_too_long_1', 'i18n_selection_too_long_n');
            } break;

            case 'wc-add-to-cart': {
                $data['gt_translate_keys'] = array('i18n_view_cart', array('key' => 'cart_url', 'format' => 'url'));
            } break;

            case 'wc-password-strength-meter': {
                $data['gt_translate_keys'] = array('i18n_password_error', 'i18n_password_hint', '');
            } break;

            default: break;
        }

        return $data;
    }

    function glt_woocommerce_geolocate_ip($false) {
        if(isset($_SERVER['HTTP_X_GT_VIEWER_IP']))
            $_SERVER['HTTP_X_REAL_IP'] = $_SERVER['HTTP_X_GT_VIEWER_IP'];
        elseif(isset($_SERVER['HTTP_X_GT_CLIENTIP']))
            $_SERVER['HTTP_X_REAL_IP'] = $_SERVER['HTTP_X_GT_CLIENTIP'];

        return $false;
    }

    add_filter('woocommerce_get_script_data', 'glt_filter_woocommerce_scripts_data', 10, 2 );

    add_filter('woocommerce_geolocate_ip', 'glt_woocommerce_geolocate_ip', 10, 4);
}

$google_language_translator = new google_language_translator();

function glt_update_option($old_value, $value, $option_name) {
    if(get_option('googlelanguagetranslator_seo_active') == '1' and get_option('googlelanguagetranslator_url_structure') == 'sub_directory') { // check if rewrite rules are in place
        $htaccess_file = get_home_path() . '.htaccess';
        // todo: use insert_with_markers functions instead
        if(wp_is_writable($htaccess_file)) {
            $htaccess = file_get_contents($htaccess_file);
            if(strpos($htaccess, 'gtranslate.php') === false) { // no config rules
                $rewrite_rules = file_get_contents(dirname(__FILE__) . '/url_addon/rewrite.txt');
                $rewrite_rules = str_replace('GLT_PLUGIN_PATH', str_replace(str_replace(array('https:', 'http:'), array(':', ':'), home_url()), '', str_replace(array('https:', 'http:'), array(':', ':'), plugins_url())) . '/google-language-translator', $rewrite_rules);

                $htaccess = $rewrite_rules . "\r\n\r\n" . $htaccess;
                if(!empty($htaccess)) { // going to update .htaccess
                    file_put_contents($htaccess_file, $htaccess);

                    add_settings_error(
                        'glt_settings_notices',
                        esc_attr( 'settings_updated' ),
                        '<p style="color:red;">' . __('.htaccess file updated', 'google-language-translator') . '</p>',
                        'updated'
                    );
                }
            }
        } else {
            $rewrite_rules = file_get_contents(dirname(__FILE__) . '/url_addon/rewrite.txt');
            $rewrite_rules = str_replace('GLT_PLUGIN_PATH', str_replace(home_url(), '', plugins_url()) . '/google-language-translator', $rewrite_rules);

            add_settings_error(
                'glt_settings_notices',
                esc_attr( 'settings_updated' ),
                '<p style="color:red;">' . __('Please add the following rules to the top of your .htaccess file', 'google-language-translator') . '</p><pre style="background-color:#eaeaea;">' . $rewrite_rules . '</pre>',
                'error'
            );
        }

        // phpcs:disable PluginCheck.CodeAnalysis.WriteFile.PluginDirectoryWrite -- Writing configuration to a local file is intentional here to avoid repeated database I/O
        // update main_lang in config.php
        $config_file = dirname(__FILE__) . '/url_addon/config.php';
        if(is_readable($config_file) and wp_is_writable($config_file)) {
            $config = file_get_contents($config_file);
            if(strpos($config, 'main_lang') !== false) {
                $config = preg_replace('/\$main_lang = \'[a-z-]{2,5}\'/i', '$main_lang = \''.get_option('googlelanguagetranslator_language').'\'', $config);
                if(is_string($config) and strlen($config) > 10)
                    file_put_contents($config_file, $config);
            }
        } else {
            add_settings_error(
                'glt_settings_notices',
                esc_attr( 'settings_updated' ),
                '<p style="color:red;">' . __('Cannot update google-language-translator/url_addon/config.php file. Make sure to update it manually and set correct $main_lang.', 'google-language-translator') . '</p>',
                'error'
            );
        }

    } else { // todo: remove rewrite rules
        // do nothing
    }
}

add_action('update_option_googlelanguagetranslator_seo_active', 'glt_update_option', 10, 3);
add_action('update_option_googlelanguagetranslator_url_structure', 'glt_update_option', 10, 3);
add_action('update_option_googlelanguagetranslator_language', 'glt_update_option', 10, 3);

// exclude javascript minification by cache plugins for free version
if($glt_seo_active != '1') {
    function cache_exclude_js_glt($excluded_js) {
        if(is_array($excluded_js) or empty($excluded_js))
            $excluded_js[] = 'cdn.gtranslate.net/widgets/latest/dropdown.js';

        return $excluded_js;
    }

    // LiteSpeed Cache
    add_filter('litespeed_optimize_js_excludes', 'cache_exclude_js_glt');

    // WP Rocket
    add_filter('rocket_exclude_js', 'cache_exclude_js_glt');
    add_filter('rocket_minify_excluded_external_js', 'cache_exclude_js_glt');
}