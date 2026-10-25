<?php
namespace MailPoetVendor\Carbon;
if (!defined('ABSPATH')) exit;
use Closure;
use DateTimeImmutable;
use DateTimeZone;
use MailPoetVendor\Psr\Clock\ClockInterface;
class FactoryImmutable extends Factory implements ClockInterface
{
protected $className = CarbonImmutable::class;
public function now($tz = null): DateTimeImmutable
{
$className = $this->className;
return new $className(null, $tz);
}
}
