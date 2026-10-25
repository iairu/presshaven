<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property\Selector;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Renderable;
interface Component extends Renderable
{
public function getValue(): string;
public function setValue(string $value): void;
public function getSpecificity(): int;
}
