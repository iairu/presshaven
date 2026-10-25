<?php
if (!defined('ABSPATH')) exit;
abstract class ActionScheduler_TimezoneHelper {
private static $local_timezone = null;
public static function set_local_timezone( DateTime $date ) {
if ( ! is_a( $date, 'ActionScheduler_DateTime' ) ) {
$date = as_get_datetime_object( $date->format( 'U' ) );
}
if ( get_option( 'timezone_string' ) ) {
$date->setTimezone( new DateTimeZone( self::get_local_timezone_string() ) );
} else {
$date->setUtcOffset( self::get_local_timezone_offset() );
}
return $date;
}
protected static function get_local_timezone_string( $reset = false ) {
$timezone = get_option( 'timezone_string' );
if ( $timezone ) {
return $timezone;
}
$utc_offset = intval( get_option( 'gmt_offset', 0 ) );
if ( 0 === $utc_offset ) {
return 'UTC';
}
$utc_offset *= 3600;
$timezone = timezone_name_from_abbr( '', $utc_offset );
if ( $timezone ) {
return $timezone;
}
foreach ( timezone_abbreviations_list() as $abbr ) {
foreach ( $abbr as $city ) {
if ( (bool) date( 'I' ) === (bool) $city['dst'] && $city['timezone_id'] && intval( $city['offset'] ) === $utc_offset ) {
return $city['timezone_id'];
}
}
}
return '';
}
protected static function get_local_timezone_offset() {
$timezone = get_option( 'timezone_string' );
if ( $timezone ) {
$timezone_object = new DateTimeZone( $timezone );
return $timezone_object->getOffset( new DateTime( 'now' ) );
} else {
return floatval( get_option( 'gmt_offset', 0 ) ) * HOUR_IN_SECONDS;
}
}
public static function get_local_timezone( $reset = false ) {
_deprecated_function( __FUNCTION__, '2.1.0', 'ActionScheduler_TimezoneHelper::set_local_timezone()' );
if ( $reset ) {
self::$local_timezone = null;
}
if ( ! isset( self::$local_timezone ) ) {
$tzstring = get_option( 'timezone_string' );
if ( empty( $tzstring ) ) {
$gmt_offset = absint( get_option( 'gmt_offset' ) );
if ( 0 === $gmt_offset ) {
$tzstring = 'UTC';
} else {
$gmt_offset *= HOUR_IN_SECONDS;
$tzstring = timezone_name_from_abbr( '', $gmt_offset, 1 );
if ( false === $tzstring ) {
$tzstring = timezone_name_from_abbr( '', $gmt_offset, 0 );
}
if ( false === $tzstring ) {
$is_dst = date( 'I' );
foreach ( timezone_abbreviations_list() as $abbr ) {
foreach ( $abbr as $city ) {
if ( $city['dst'] === $is_dst && $city['offset'] === $gmt_offset ) {
if ( is_null( $city['timezone_id'] ) ) {
continue;
}
$tzstring = $city['timezone_id'];
break 2;
}
}
}
}
if ( false === $tzstring ) {
$tzstring = 'UTC';
}
}
}
self::$local_timezone = new DateTimeZone( $tzstring );
}
return self::$local_timezone;
}
}
