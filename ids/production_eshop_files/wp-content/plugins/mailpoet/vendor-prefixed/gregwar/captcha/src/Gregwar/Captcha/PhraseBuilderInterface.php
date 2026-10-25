<?php
namespace MailPoetVendor\Gregwar\Captcha;
if (!defined('ABSPATH')) exit;
interface PhraseBuilderInterface
{
public function build($length = null, $charset = null);
public function niceize($str);
}
