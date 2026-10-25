<?php
/**
* Noting Found Page Settings.
*
* @package Omega Storefront
*/

$omega_storefront_default = omega_storefront_get_default_theme_options();

$wp_customize->add_section( 'omega_storefront_noting_found_page_settings',
    array(
        'title'      => esc_html__( 'Nothing Found Page Settings', 'omega-storefront' ),
        'priority'   => 200,
        'capability' => 'edit_theme_options',
        'panel'      => 'omega_storefront_theme_addons_panel',
    )
);

$wp_customize->add_setting( 'omega_storefront_noting_found_main_title',
    array(
        'default'           => 'Nothing Found',
        'capability'        => 'edit_theme_options',
        'sanitize_callback' => 'sanitize_text_field',
    )
);
$wp_customize->add_control( 'omega_storefront_noting_found_main_title',
    array(
        'label'    => esc_html__( 'Main Title', 'omega-storefront' ),
        'section'  => 'omega_storefront_noting_found_page_settings',
        'type'     => 'text',
    )
);

$wp_customize->add_setting( 'omega_storefront_noting_found_para',
    array(
        'default'           => 'Sorry, but nothing matched your search terms. Please try again with some different keywords.',
        'capability'        => 'edit_theme_options',
        'sanitize_callback' => 'sanitize_text_field',
    )
);
$wp_customize->add_control( 'omega_storefront_noting_found_para',
    array(
        'label'    => esc_html__( 'Para Text', 'omega-storefront' ),
        'section'  => 'omega_storefront_noting_found_page_settings',
        'type'     => 'text',
    )
);

$wp_customize->add_setting('omega_storefront_noting_found_saerch',
    array(
        'default' => 1,
        'capability' => 'edit_theme_options',
        'sanitize_callback' => 'omega_storefront_sanitize_checkbox',
    )
);
$wp_customize->add_control('omega_storefront_noting_found_saerch',
    array(
        'label' => esc_html__('Enable/Disable Search', 'omega-storefront'),
        'section' => 'omega_storefront_noting_found_page_settings',
        'type' => 'checkbox',
    )
);