<?php
namespace Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Parser\Shortcut;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Node\ElementNode;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Node\SelectorNode;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Parser\ParserInterface;
class ElementParser implements ParserInterface
{
public function parse(string $source): array
{
if (preg_match('/^(?:([a-z]++)\|)?([\w-]++|\*)$/i', trim($source), $matches)) {
return [new SelectorNode(new ElementNode($matches[1] ?: null, $matches[2]))];
}
return [];
}
}
