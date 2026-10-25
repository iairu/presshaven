<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\RuleSet;
if (!defined('ABSPATH')) exit;
if (!\class_exists(RuleContainer::class, \false) && !\interface_exists(RuleContainer::class, \false)) {
$aliasWasCreated = \class_alias(DeclarationList::class, RuleContainer::class);
\assert($aliasWasCreated);
if (!\class_exists(RuleContainer::class, \false) && !\interface_exists(RuleContainer::class, \false)) {
interface RuleContainer
{
}
}
}
