<?php
if(!defined('ABSPATH'))
    exit;

class glt_widget extends WP_Widget {
    function __construct() {
        parent::__construct(
            'glt_widget', __('Google Language Translator', 'google-language-translator'), array( 'description' => __( 'Add the Google Language Translator website tool.', 'google-language-translator' ), )
        );
    }

    public function widget( $args, $instance ) {
        $title = apply_filters( 'widget_title', $instance['title'] );
        echo wp_kses_post($args['before_widget']);
        if ( ! empty( $title ) )
            echo wp_kses_post($args['before_title']) . esc_html($title) . wp_kses_post($args['after_title']);
        echo wp_kses_post(do_shortcode('[google-translator]'));
        echo wp_kses_post($args['after_widget']);
    }

    public function form( $instance ) {
        if ( isset( $instance[ 'title' ] ) ) {
            $title = $instance[ 'title' ];
        } else {
            $title = __( 'Translate:', 'google-language-translator' );
        } ?>

        <p><label for="<?php echo esc_attr($this->get_field_id( 'title' )); ?>"><?php esc_attr_e( 'Title:', 'google-language-translator'); ?></label><input class="widefat" id="<?php echo esc_attr($this->get_field_id( 'title' )); ?>" name="<?php echo esc_attr($this->get_field_name( 'title' )); ?>" type="text" value="<?php echo esc_attr( $title ); ?>"></p>
        <?php
    }

    public function update( $new_instance, $old_instance ) {
        $instance = array();
        $instance['title'] = ( ! empty( $new_instance['title'] ) ) ? wp_strip_all_tags( $new_instance['title'] ) : '';
        return $instance;
    }
} // class glt_widget

function register_glt_widget() {
    register_widget( 'glt_widget' );
}

add_action( 'widgets_init', 'register_glt_widget' );