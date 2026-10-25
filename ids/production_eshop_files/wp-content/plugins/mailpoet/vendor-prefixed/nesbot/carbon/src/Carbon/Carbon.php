<?php
namespace MailPoetVendor\Carbon;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Carbon\Traits\Date;
use MailPoetVendor\Carbon\Traits\DeprecatedProperties;
use DateTime;
use DateTimeInterface;
use DateTimeZone;
class Carbon extends DateTime implements CarbonInterface
{
use Date;
public static function isMutable()
{
return \true;
}
}
