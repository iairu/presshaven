<?php
namespace MailPoetVendor\Twig\NodeVisitor;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Twig\Environment;
use MailPoetVendor\Twig\Node\Node;
abstract class AbstractNodeVisitor implements NodeVisitorInterface
{
final public function enterNode(Node $node, Environment $env): Node
{
return $this->doEnterNode($node, $env);
}
final public function leaveNode(Node $node, Environment $env): ?Node
{
return $this->doLeaveNode($node, $env);
}
abstract protected function doEnterNode(Node $node, Environment $env);
abstract protected function doLeaveNode(Node $node, Environment $env);
}
