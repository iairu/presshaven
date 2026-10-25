<?php
namespace Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Parser\Shortcut;
if (!defined('ABSPATH')) exit;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Node\ClassNode;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Node\ElementNode;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Node\SelectorNode;
use Automattic\WooCommerce\EmailEditorVendor\Symfony\Component\CssSelector\Parser\ParserInterface;
class ClassParser implements ParserInterface
{
public function parse(string $source): array
{
if (preg_match('/^(?:([a-z]++)\|)?+([\w-]++|\*)?+\.([\w-]++)$/i', trim($source), $matches)) {
return [
new SelectorNode(new ClassNode(new ElementNode($matches[1] ?: null, $matches[2] ?: null), $matches[3])),
];
}
return [];
}
}
