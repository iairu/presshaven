<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Rule;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Property\Declaration;
if (!\class_exists(Rule::class, \false) && !\interface_exists(Rule::class, \false)) {
$aliasWasCreated = \class_alias(Declaration::class, Rule::class);
\assert($aliasWasCreated);
if (!\class_exists(Rule::class, \false) && !\interface_exists(Rule::class, \false)) {
class Rule
{
}
}
}
