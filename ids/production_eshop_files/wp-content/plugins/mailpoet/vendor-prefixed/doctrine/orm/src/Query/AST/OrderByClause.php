<?php
declare (strict_types=1);
namespace MailPoetVendor\Doctrine\ORM\Query\AST;
if (!defined('ABSPATH')) exit;
class OrderByClause extends Node
{
public $orderByItems = [];
public $includeCollectionOrderByItems = \true;
public function __construct(array $orderByItems, bool $includeCollectionOrderByItems = \true)
{
$this->orderByItems = $orderByItems;
$this->includeCollectionOrderByItems = $includeCollectionOrderByItems;
}
public function dispatch($sqlWalker)
{
return $sqlWalker->walkOrderByClause($this);
}
}
