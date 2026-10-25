<?php
declare (strict_types=1);
namespace MailPoetVendor\Sabberworm\CSS\Property\Selector;
if (!defined('ABSPATH')) exit;
final class SpecificityCalculator
{
private const NON_ID_ATTRIBUTES_AND_PSEUDO_CLASSES_RX = '/
        (\.[\w]+)                   # classes
        |
        \[(\w+)                     # attributes
        |
        (\:(                         # pseudo classes
            link|visited|active
            |hover|focus
            |lang
            |target
            |enabled|disabled|checked|indeterminate
            |root
            |nth-child|nth-last-child|nth-of-type|nth-last-of-type
            |first-child|last-child|first-of-type|last-of-type
            |only-child|only-of-type
            |empty|contains
        ))
        /ix';
private const ELEMENTS_AND_PSEUDO_ELEMENTS_RX = '/
        ((^|[\s\+\>\~]+)[\w]+   # elements
        |
        \:{1,2}(                    # pseudo-elements
            after|before|first-letter|first-line|selection
        ))
        /ix';
private static $cache = [];
public static function calculate(string $selector): int
{
if (!isset(self::$cache[$selector])) {
$a = 0;
$matches = null;
$b = \substr_count($selector, '#');
$c = \preg_match_all(self::NON_ID_ATTRIBUTES_AND_PSEUDO_CLASSES_RX, $selector, $matches);
\assert(\is_int($c));
$d = \preg_match_all(self::ELEMENTS_AND_PSEUDO_ELEMENTS_RX, $selector, $matches);
\assert(\is_int($d));
self::$cache[$selector] = $a * 1000 + $b * 100 + $c * 10 + $d;
}
return self::$cache[$selector];
}
public static function clearCache(): void
{
self::$cache = [];
}
}
