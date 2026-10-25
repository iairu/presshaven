<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\CSSList\CSSListItem;
interface AtRule extends CSSListItem
{
public const BLOCK_RULES = ['media', 'document', 'supports', 'region-style', 'font-feature-values', 'container', 'layer', 'scope', 'starting-style'];
public function atRuleName(): string;
}
