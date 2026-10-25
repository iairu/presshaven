<?php
declare (strict_types=1);
namespace MailPoetVendor\Pelago\Emogrifier\HtmlProcessor;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Pelago\Emogrifier\Utilities\DeclarationBlockParser;
use MailPoetVendor\Pelago\Emogrifier\Utilities\Preg;
final class CssVariableEvaluator extends AbstractHtmlProcessor
{
private $currentVariableDefinitions = [];
public function evaluateVariables(): self
{
$elementsToEvaluate = [['element' => $this->getHtmlElement(), 'ancestorDefinitions' => []]];
while (($currentElementData = \array_pop($elementsToEvaluate)) !== null) {
$currentElement = $currentElementData['element'];
$currentAncestorDefinitions = $currentElementData['ancestorDefinitions'];
$style = $currentElement->getAttribute('style');
if ((new Preg())->match('/(?<![\w\-])--[\w\-]/', $style) !== 0) {
$declarations = DeclarationBlockParser::parse($style);
$variableDefinitions = $this->getVariableDefinitionsFromDeclarations($declarations) + $currentAncestorDefinitions;
$this->currentVariableDefinitions = $variableDefinitions;
$newDeclarations = $this->replaceVariablesInDeclarations($declarations);
if ($newDeclarations !== null) {
$currentElement->setAttribute('style', $this->getDeclarationsAsString($newDeclarations));
}
} else {
$variableDefinitions = $currentAncestorDefinitions;
}
foreach ($currentElement->childNodes as $child) {
if ($child instanceof \DOMElement) {
$elementsToEvaluate[] = ['element' => $child, 'ancestorDefinitions' => $variableDefinitions];
}
}
}
return $this;
}
private function getVariableDefinitionsFromDeclarations(array $declarations): array
{
return \array_filter($declarations, static function (string $key): bool {
return \substr($key, 0, 2) === '--';
}, \ARRAY_FILTER_USE_KEY);
}
private function getPropertyValueReplacement(array $matches): string
{
\assert(\is_string($matches[1] ?? null));
$variableName = $matches[1];
if (isset($this->currentVariableDefinitions[$variableName])) {
$variableValue = $this->currentVariableDefinitions[$variableName];
} else {
$fallbackValueSeparator = $matches[2] ?? '';
if ($fallbackValueSeparator !== '') {
\assert(\is_string($matches[3] ?? null));
$fallbackValue = $matches[3];
$variableValue = $this->replaceVariablesInPropertyValue($fallbackValue);
} else {
$variableValue = $matches[0];
}
}
return $variableValue;
}
private function replaceVariablesInPropertyValue(string $propertyValue): string
{
$pattern = '/
                var\(
                    \s*+
                    # capture variable name including `--` prefix
                    (
                        --[^\s\),]++
                    )
                    \s*+
                    # capture optional fallback value
                    (?:
                        # capture separator to confirm there is a fallback value
                        (,)\s*
                        # begin capture with named group that can be used recursively
                        (?<recursable>
                            # begin named group to match sequence without parentheses, except in strings
                            (?<noparentheses>
                                # repeated zero or more times:
                                (?:
                                    # sequence without parentheses or quotes
                                    [^\(\)\'"]++
                                    |
                                    # string in double quotes
                                    "(?>[^"\\\\]++|\\\\.)*"
                                    |
                                    # string in single quotes
                                    \'(?>[^\'\\\\]++|\\\\.)*\'
                                )*+
                            )
                            # repeated zero or more times:
                            (?:
                                # sequence in parentheses
                                \(
                                    # using the named recursable pattern
                                    (?&recursable)
                                \)
                                # sequence without parentheses, except in strings
                                (?&noparentheses)
                            )*+
                        )
                    )?+
                \)
            /x';
$callable = \Closure::fromCallable([$this, 'getPropertyValueReplacement']);
return (new Preg())->replaceCallback($pattern, $callable, $propertyValue);
}
private function replaceVariablesInDeclarations(array $declarations): ?array
{
$substitutionsMade = \false;
$result = \array_map(function (string $propertyValue) use (&$substitutionsMade): string {
$newPropertyValue = $this->replaceVariablesInPropertyValue($propertyValue);
if ($newPropertyValue !== $propertyValue) {
$substitutionsMade = \true;
}
return $newPropertyValue;
}, $declarations);
return $substitutionsMade ? $result : null;
}
private function getDeclarationsAsString(array $declarations): string
{
$declarationStrings = \array_map(static function (string $key, string $value): string {
return $key . ': ' . $value;
}, \array_keys($declarations), \array_values($declarations));
return \implode('; ', $declarationStrings) . ';';
}
}
