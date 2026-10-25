<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS;
if (!defined('ABSPATH')) exit;
trait ShortClassNameProvider
{
private function getShortClassName(): string
{
return (new \ReflectionClass($this))->getShortName();
}
}
