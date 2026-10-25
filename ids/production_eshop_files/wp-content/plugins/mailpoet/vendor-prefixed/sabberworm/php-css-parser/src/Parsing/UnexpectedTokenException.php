<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Parsing;
if (!defined('ABSPATH')) exit;
class UnexpectedTokenException extends SourceException
{
public function __construct(string $expected, string $found, string $matchType = 'literal', ?int $lineNumber = null)
{
$message = "Token “{$expected}” ({$matchType}) not found. Got “{$found}”.";
if ($matchType === 'search') {
$message = "Search for “{$expected}” returned no results. Context: “{$found}”.";
} elseif ($matchType === 'count') {
$message = "Next token was expected to have {$expected} chars. Context: “{$found}”.";
} elseif ($matchType === 'identifier') {
$message = "Identifier expected. Got “{$found}”";
} elseif ($matchType === 'custom') {
$message = \trim("{$expected} {$found}");
}
parent::__construct($message, $lineNumber);
}
}
