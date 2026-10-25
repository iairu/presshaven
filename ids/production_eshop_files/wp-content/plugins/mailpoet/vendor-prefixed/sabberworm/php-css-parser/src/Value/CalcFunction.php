<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Value;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Sabberworm\CSS\Parsing\ParserState;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedEOFException;
use MailPoetVendor\Sabberworm\CSS\Parsing\UnexpectedTokenException;
class CalcFunction extends CSSFunction
{
private const T_OPERAND = 1;
private const T_OPERATOR = 2;
public static function parse(ParserState $parserState, bool $ignoreCase = \false): CSSFunction
{
$operators = ['+', '-', '*', '/'];
$function = $parserState->parseIdentifier();
if ($parserState->peek() !== '(') {
throw new UnexpectedTokenException('(', $parserState->peek(), 'literal', $parserState->currentLine());
} elseif ($function !== 'calc') {
throw new UnexpectedTokenException('calc', $function, 'literal', $parserState->currentLine());
}
$parserState->consume('(');
$calcRuleValueList = new CalcRuleValueList($parserState->currentLine());
$list = new RuleValueList(',', $parserState->currentLine());
$nestingLevel = 0;
$lastComponentType = null;
while (!$parserState->comes(')') || $nestingLevel > 0) {
if ($parserState->isEnd() && $nestingLevel === 0) {
break;
}
$parserState->consumeWhiteSpace();
if ($parserState->comes('(')) {
$nestingLevel++;
$calcRuleValueList->addListComponent($parserState->consume(1));
$parserState->consumeWhiteSpace();
continue;
} elseif ($parserState->comes(')')) {
$nestingLevel--;
$calcRuleValueList->addListComponent($parserState->consume(1));
$parserState->consumeWhiteSpace();
continue;
}
if ($lastComponentType !== CalcFunction::T_OPERAND) {
$value = Value::parsePrimitiveValue($parserState);
$calcRuleValueList->addListComponent($value);
$lastComponentType = CalcFunction::T_OPERAND;
} else if (\in_array($parserState->peek(), $operators, \true)) {
if ($parserState->comes('-') || $parserState->comes('+')) {
$matchResultBefore = \preg_match('/\s/', $parserState->peek(1, -1));
\assert(\is_int($matchResultBefore));
$matchResultAfter = \preg_match('/\s/', $parserState->peek(1, 1));
\assert(\is_int($matchResultAfter));
if ($matchResultBefore !== 1 || $matchResultAfter !== 1) {
throw new UnexpectedTokenException(" {$parserState->peek()} ", $parserState->peek(1, -1) . $parserState->peek(2), 'literal', $parserState->currentLine());
}
}
$calcRuleValueList->addListComponent($parserState->consume(1));
$lastComponentType = CalcFunction::T_OPERATOR;
} else {
throw new UnexpectedTokenException(\sprintf('Next token was expected to be an operand of type %s. Instead "%s" was found.', \implode(', ', $operators), $parserState->peek()), '', 'custom', $parserState->currentLine());
}
$parserState->consumeWhiteSpace();
}
$list->addListComponent($calcRuleValueList);
if (!$parserState->isEnd()) {
$parserState->consume(')');
}
return new CalcFunction($function, $list, ',', $parserState->currentLine());
}
public function getArrayRepresentation(): array
{
throw new \BadMethodCallException('`getArrayRepresentation` is not yet implemented for `' . self::class . '`');
}
}
