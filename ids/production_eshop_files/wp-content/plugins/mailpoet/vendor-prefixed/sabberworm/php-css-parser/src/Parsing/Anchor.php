<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Parsing;
if (!defined('ABSPATH')) exit;
class Anchor
{
private $position;
private $parserState;
public function __construct(int $position, ParserState $parserState)
{
$this->position = $position;
$this->parserState = $parserState;
}
public function backtrack(): void
{
$this->parserState->setPosition($this->position);
}
}
