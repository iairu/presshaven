<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
class RuleValueList extends ValueList
{
public function __construct(string $separator = ',', ?int $lineNumber = null)
{
parent::__construct([], $separator, $lineNumber);
}
}
