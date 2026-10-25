<?php
namespace MailPoetVendor\Symfony\Component\Validator\Constraints;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Symfony\Component\Validator\Constraint;
use MailPoetVendor\Symfony\Component\Validator\Exception\InvalidArgumentException;
#[\Attribute(\Attribute::TARGET_PROPERTY | \Attribute::TARGET_METHOD | \Attribute::IS_REPEATABLE)]
class Regex extends Constraint
{
public const REGEX_FAILED_ERROR = 'de1e3db3-5ed4-4941-aae4-59f3667cc3a3';
protected static $errorNames = [self::REGEX_FAILED_ERROR => 'REGEX_FAILED_ERROR'];
public $message = 'This value is not valid.';
public $pattern;
public $htmlPattern;
public $match = \true;
public $normalizer;
public function __construct($pattern, ?string $message = null, ?string $htmlPattern = null, ?bool $match = null, ?callable $normalizer = null, ?array $groups = null, $payload = null, array $options = [])
{
if (\is_array($pattern)) {
$options = array_merge($pattern, $options);
} elseif (null !== $pattern) {
$options['value'] = $pattern;
}
parent::__construct($options, $groups, $payload);
$this->message = $message ?? $this->message;
$this->htmlPattern = $htmlPattern ?? $this->htmlPattern;
$this->match = $match ?? $this->match;
$this->normalizer = $normalizer ?? $this->normalizer;
if (null !== $this->normalizer && !\is_callable($this->normalizer)) {
throw new InvalidArgumentException(sprintf('The "normalizer" option must be a valid callable ("%s" given).', get_debug_type($this->normalizer)));
}
}
public function getDefaultOption()
{
return 'pattern';
}
public function getRequiredOptions()
{
return ['pattern'];
}
public function getHtmlPattern()
{
if (null !== $this->htmlPattern) {
return empty($this->htmlPattern) ? null : $this->htmlPattern;
}
if ($this->pattern[0] !== $this->pattern[\strlen($this->pattern) - 1]) {
return null;
}
$delimiter = $this->pattern[0];
$pattern = str_replace('\\' . $delimiter, $delimiter, substr($this->pattern, 1, -1));
if (!$this->match) {
return '((?!' . $pattern . ').)*';
}
if (str_contains($pattern, '|')) {
return '.*(' . $pattern . ').*';
}
$pattern = '^' === $pattern[0] ? substr($pattern, 1) : '.*' . $pattern;
$pattern = '$' === $pattern[\strlen($pattern) - 1] ? substr($pattern, 0, -1) : $pattern . '.*';
return $pattern;
}
}
