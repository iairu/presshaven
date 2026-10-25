<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Query\AST;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Doctrine\Deprecations\Deprecation;
class InExpression extends Node
{
public $not;
public $expression;
public $literals = [];
public $subselect;
public function __construct($expression)
{
if (!$this instanceof InListExpression && !$this instanceof InSubselectExpression) {
Deprecation::trigger('doctrine/orm', 'https://github.com/doctrine/orm/pull/10267', '%s is deprecated, use %s or %s instead.', self::class, InListExpression::class, InSubselectExpression::class);
}
$this->expression = $expression;
}
public function dispatch($sqlWalker)
{
return $sqlWalker->walkInExpression($this);
}
}
