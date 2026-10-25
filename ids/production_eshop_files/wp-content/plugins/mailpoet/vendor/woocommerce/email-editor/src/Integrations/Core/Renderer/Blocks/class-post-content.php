<?php
declare( strict_types = 1 );
namespace Automattic\WooCommerce\EmailEditor\Integrations\Core\Renderer\Blocks;
if (!defined('ABSPATH')) exit;
class Post_Content {
public function render_stateless( $attributes, $content, $block ): string {
$post_id = $block->context['postId'] ?? null;
if ( $post_id ) {
$email_post = get_post( $post_id );
} elseif ( isset( $GLOBALS['post'] ) && $GLOBALS['post'] instanceof \WP_Post && 0 === $GLOBALS['post']->ID ) {
$email_post = $GLOBALS['post'];
} else {
return '';
}
if ( ! $email_post || empty( $email_post->post_content ) ) {
return '';
}
global $post, $wp_query;
$backup_post = $post;
$backup_query = $wp_query;
$post = $email_post;
if ( $email_post->ID > 0 ) {
$wp_query = new \WP_Query( array( 'p' => $email_post->ID ) );
} else {
$wp_query = new \WP_Query();
$wp_query->post = $email_post;
$wp_query->posts = array( $email_post );
$wp_query->post_count = 1;
$wp_query->found_posts = 1;
}
$post_content = $email_post->post_content;
if ( has_block( 'core/nextpage', $email_post ) ) {
$post_content .= wp_link_pages( array( 'echo' => 0 ) );
}
$post_content = apply_filters( 'the_content', str_replace( ']]>', ']]&gt;', $post_content ) );
$post = $backup_post;
$wp_query = $backup_query;
if ( empty( $post_content ) ) {
return '';
}
return $post_content;
}
}
