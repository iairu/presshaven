<?php
namespace MailPoetVendor\Symfony\Polyfill\Intl\Idn;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Symfony\Polyfill\Intl\Idn\Resources\unidata\DisallowedRanges;
use MailPoetVendor\Symfony\Polyfill\Intl\Idn\Resources\unidata\Regex;
final class Idn
{
public const ERROR_EMPTY_LABEL = 1;
public const ERROR_LABEL_TOO_LONG = 2;
public const ERROR_DOMAIN_NAME_TOO_LONG = 4;
public const ERROR_LEADING_HYPHEN = 8;
public const ERROR_TRAILING_HYPHEN = 0x10;
public const ERROR_HYPHEN_3_4 = 0x20;
public const ERROR_LEADING_COMBINING_MARK = 0x40;
public const ERROR_DISALLOWED = 0x80;
public const ERROR_PUNYCODE = 0x100;
public const ERROR_LABEL_HAS_DOT = 0x200;
public const ERROR_INVALID_ACE_LABEL = 0x400;
public const ERROR_BIDI = 0x800;
public const ERROR_CONTEXTJ = 0x1000;
public const ERROR_CONTEXTO_PUNCTUATION = 0x2000;
public const ERROR_CONTEXTO_DIGITS = 0x4000;
public const INTL_IDNA_VARIANT_2003 = 0;
public const INTL_IDNA_VARIANT_UTS46 = 1;
public const IDNA_DEFAULT = 0;
public const IDNA_ALLOW_UNASSIGNED = 1;
public const IDNA_USE_STD3_RULES = 2;
public const IDNA_CHECK_BIDI = 4;
public const IDNA_CHECK_CONTEXTJ = 8;
public const IDNA_NONTRANSITIONAL_TO_ASCII = 16;
public const IDNA_NONTRANSITIONAL_TO_UNICODE = 32;
public const MAX_DOMAIN_SIZE = 253;
public const MAX_LABEL_SIZE = 63;
public const BASE = 36;
public const TMIN = 1;
public const TMAX = 26;
public const SKEW = 38;
public const DAMP = 700;
public const INITIAL_BIAS = 72;
public const INITIAL_N = 128;
public const DELIMITER = '-';
public const MAX_INT = 2147483647;
private static $basicToDigit = [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, -1, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1];
private static $virama;
private static $mapped;
private static $ignored;
private static $deviation;
private static $disallowed;
private static $disallowed_STD3_mapped;
private static $disallowed_STD3_valid;
private static $mappingTableLoaded = \false;
public static function idn_to_ascii($domainName, $options = self::IDNA_DEFAULT, $variant = self::INTL_IDNA_VARIANT_UTS46, &$idna_info = [])
{
if (\PHP_VERSION_ID > 80400 && '' === $domainName) {
throw new \ValueError('idn_to_ascii(): Argument #1 ($domain) cannot be empty');
}
if (self::INTL_IDNA_VARIANT_2003 === $variant) {
@trigger_error('idn_to_ascii(): INTL_IDNA_VARIANT_2003 is deprecated', \E_USER_DEPRECATED);
}
$options = ['CheckHyphens' => \true, 'CheckBidi' => self::INTL_IDNA_VARIANT_2003 === $variant || 0 !== ($options & self::IDNA_CHECK_BIDI), 'CheckJoiners' => self::INTL_IDNA_VARIANT_UTS46 === $variant && 0 !== ($options & self::IDNA_CHECK_CONTEXTJ), 'UseSTD3ASCIIRules' => 0 !== ($options & self::IDNA_USE_STD3_RULES), 'Transitional_Processing' => self::INTL_IDNA_VARIANT_2003 === $variant || 0 === ($options & self::IDNA_NONTRANSITIONAL_TO_ASCII), 'VerifyDnsLength' => \true];
$info = new Info();
$labels = self::process((string) $domainName, $options, $info);
foreach ($labels as $i => $label) {
if (1 === preg_match('/[^\x00-\x7F]/', $label)) {
try {
$label = 'xn--' . self::punycodeEncode($label);
} catch (\Exception $e) {
$info->errors |= self::ERROR_PUNYCODE;
}
$labels[$i] = $label;
}
}
if ($options['VerifyDnsLength']) {
self::validateDomainAndLabelLength($labels, $info);
}
$idna_info = ['result' => implode('.', $labels), 'isTransitionalDifferent' => $info->transitionalDifferent, 'errors' => $info->errors];
return 0 === $info->errors ? $idna_info['result'] : \false;
}
public static function idn_to_utf8($domainName, $options = self::IDNA_DEFAULT, $variant = self::INTL_IDNA_VARIANT_UTS46, &$idna_info = [])
{
if (\PHP_VERSION_ID > 80400 && '' === $domainName) {
throw new \ValueError('idn_to_utf8(): Argument #1 ($domain) cannot be empty');
}
if (self::INTL_IDNA_VARIANT_2003 === $variant) {
@trigger_error('idn_to_utf8(): INTL_IDNA_VARIANT_2003 is deprecated', \E_USER_DEPRECATED);
}
$info = new Info();
$labels = self::process((string) $domainName, ['CheckHyphens' => \true, 'CheckBidi' => self::INTL_IDNA_VARIANT_2003 === $variant || 0 !== ($options & self::IDNA_CHECK_BIDI), 'CheckJoiners' => self::INTL_IDNA_VARIANT_UTS46 === $variant && 0 !== ($options & self::IDNA_CHECK_CONTEXTJ), 'UseSTD3ASCIIRules' => 0 !== ($options & self::IDNA_USE_STD3_RULES), 'Transitional_Processing' => self::INTL_IDNA_VARIANT_2003 === $variant || 0 === ($options & self::IDNA_NONTRANSITIONAL_TO_UNICODE)], $info);
$idna_info = ['result' => implode('.', $labels), 'isTransitionalDifferent' => $info->transitionalDifferent, 'errors' => $info->errors];
return 0 === $info->errors ? $idna_info['result'] : \false;
}
private static function isValidContextJ(array $codePoints, $label)
{
if (!isset(self::$virama)) {
self::$virama = require __DIR__ . \DIRECTORY_SEPARATOR . 'Resources' . \DIRECTORY_SEPARATOR . 'unidata' . \DIRECTORY_SEPARATOR . 'virama.php';
}
$offset = 0;
foreach ($codePoints as $i => $codePoint) {
if (0x200c !== $codePoint && 0x200d !== $codePoint) {
continue;
}
if (!isset($codePoints[$i - 1])) {
return \false;
}
if (isset(self::$virama[$codePoints[$i - 1]])) {
continue;
}
if (0x200c === $codePoint && 1 === preg_match(Regex::ZWNJ, $label, $matches, \PREG_OFFSET_CAPTURE, $offset)) {
$offset += \strlen($matches[1][0]);
continue;
}
return \false;
}
return \true;
}
private static function mapCodePoints($input, array $options, Info $info)
{
$str = '';
$useSTD3ASCIIRules = $options['UseSTD3ASCIIRules'];
$transitional = $options['Transitional_Processing'];
foreach (self::utf8Decode($input) as $codePoint) {
$data = self::lookupCodePointStatus($codePoint, $useSTD3ASCIIRules);
switch ($data['status']) {
case 'disallowed':
case 'valid':
$str .= mb_chr($codePoint, 'utf-8');
break;
case 'ignored':
break;
case 'mapped':
$str .= $transitional && 0x1e9e === $codePoint ? 'ss' : $data['mapping'];
break;
case 'deviation':
$info->transitionalDifferent = \true;
$str .= $transitional ? $data['mapping'] : mb_chr($codePoint, 'utf-8');
break;
}
}
return $str;
}
private static function process($domain, array $options, Info $info)
{
$checkForEmptyLabels = !isset($options['VerifyDnsLength']) || $options['VerifyDnsLength'];
if ($checkForEmptyLabels && '' === $domain) {
$info->errors |= self::ERROR_EMPTY_LABEL;
return [$domain];
}
$domain = self::mapCodePoints($domain, $options, $info);
if (!\MailPoetVendor\Normalizer::isNormalized($domain, \MailPoetVendor\Normalizer::FORM_C)) {
$domain = \MailPoetVendor\Normalizer::normalize($domain, \MailPoetVendor\Normalizer::FORM_C);
}
$labels = explode('.', $domain);
$lastLabelIndex = \count($labels) - 1;
foreach ($labels as $i => $label) {
$validationOptions = $options;
if ('xn--' === substr($label, 0, 4)) {
if (preg_match('/[^\x00-\x7F]/', $label)) {
$info->errors |= self::ERROR_PUNYCODE;
continue;
}
try {
$label = self::punycodeDecode(substr($label, 4));
} catch (\Exception $e) {
$info->errors |= self::ERROR_PUNYCODE;
continue;
}
if ('' === $label || 1 !== preg_match('/[^\x00-\x7F]/', $label)) {
$info->errors |= self::ERROR_INVALID_ACE_LABEL;
continue;
}
$validationOptions['Transitional_Processing'] = \false;
$labels[$i] = $label;
}
self::validateLabel($label, $info, $validationOptions, $i > 0 && $i === $lastLabelIndex);
}
if ($info->bidiDomain && !$info->validBidiDomain) {
$info->errors |= self::ERROR_BIDI;
}
return $labels;
}
private static function validateBidiLabel($label, Info $info)
{
if (1 === preg_match(Regex::RTL_LABEL, $label)) {
$info->bidiDomain = \true;
if (1 !== preg_match(Regex::BIDI_STEP_1_RTL, $label)) {
$info->validBidiDomain = \false;
return;
}
if (1 === preg_match(Regex::BIDI_STEP_2, $label)) {
$info->validBidiDomain = \false;
return;
}
if (1 !== preg_match(Regex::BIDI_STEP_3, $label)) {
$info->validBidiDomain = \false;
return;
}
if (1 === preg_match(Regex::BIDI_STEP_4_AN, $label) && 1 === preg_match(Regex::BIDI_STEP_4_EN, $label)) {
$info->validBidiDomain = \false;
return;
}
return;
}
if (1 !== preg_match(Regex::BIDI_STEP_1_LTR, $label)) {
$info->validBidiDomain = \false;
return;
}
if (1 === preg_match(Regex::BIDI_STEP_5, $label)) {
$info->validBidiDomain = \false;
return;
}
if (1 !== preg_match(Regex::BIDI_STEP_6, $label)) {
$info->validBidiDomain = \false;
return;
}
}
private static function validateDomainAndLabelLength(array $labels, Info $info)
{
$maxDomainSize = self::MAX_DOMAIN_SIZE;
$length = \count($labels);
$domainLength = $length - 1;
if ($length > 1 && '' === $labels[$length - 1]) {
++$maxDomainSize;
--$length;
}
for ($i = 0; $i < $length; ++$i) {
$bytes = \strlen($labels[$i]);
$domainLength += $bytes;
if ($bytes > self::MAX_LABEL_SIZE) {
$info->errors |= self::ERROR_LABEL_TOO_LONG;
}
}
if ($domainLength > $maxDomainSize) {
$info->errors |= self::ERROR_DOMAIN_NAME_TOO_LONG;
}
}
private static function validateLabel($label, Info $info, array $options, $canBeEmpty)
{
if ('' === $label) {
if (!$canBeEmpty && (!isset($options['VerifyDnsLength']) || $options['VerifyDnsLength'])) {
$info->errors |= self::ERROR_EMPTY_LABEL;
}
return;
}
if (!\MailPoetVendor\Normalizer::isNormalized($label, \MailPoetVendor\Normalizer::FORM_C)) {
$info->errors |= self::ERROR_INVALID_ACE_LABEL;
}
$codePoints = self::utf8Decode($label);
if ($options['CheckHyphens']) {
if (isset($codePoints[2], $codePoints[3]) && 0x2d === $codePoints[2] && 0x2d === $codePoints[3]) {
$info->errors |= self::ERROR_HYPHEN_3_4;
}
if ('-' === substr($label, 0, 1)) {
$info->errors |= self::ERROR_LEADING_HYPHEN;
}
if ('-' === substr($label, -1, 1)) {
$info->errors |= self::ERROR_TRAILING_HYPHEN;
}
} elseif ('xn--' === substr($label, 0, 4)) {
$info->errors |= self::ERROR_PUNYCODE;
}
if (\false !== strpos($label, '.')) {
$info->errors |= self::ERROR_LABEL_HAS_DOT;
}
if (1 === preg_match(Regex::COMBINING_MARK, $label)) {
$info->errors |= self::ERROR_LEADING_COMBINING_MARK;
}
$transitional = $options['Transitional_Processing'];
$useSTD3ASCIIRules = $options['UseSTD3ASCIIRules'];
foreach ($codePoints as $codePoint) {
$data = self::lookupCodePointStatus($codePoint, $useSTD3ASCIIRules);
$status = $data['status'];
if ('valid' === $status || !$transitional && 'deviation' === $status) {
continue;
}
$info->errors |= self::ERROR_DISALLOWED;
break;
}
if ($options['CheckJoiners'] && !self::isValidContextJ($codePoints, $label)) {
$info->errors |= self::ERROR_CONTEXTJ;
}
if ($options['CheckBidi'] && (!$info->bidiDomain || $info->validBidiDomain)) {
self::validateBidiLabel($label, $info);
}
}
private static function punycodeDecode($input)
{
$n = self::INITIAL_N;
$out = 0;
$i = 0;
$bias = self::INITIAL_BIAS;
$lastDelimIndex = strrpos($input, self::DELIMITER);
$b = \false === $lastDelimIndex ? 0 : $lastDelimIndex;
$inputLength = \strlen($input);
$output = [];
$bytes = array_map('ord', str_split($input));
for ($j = 0; $j < $b; ++$j) {
if ($bytes[$j] > 0x7f) {
throw new \Exception('Invalid input');
}
$output[$out++] = $input[$j];
}
if ($b > 0) {
++$b;
}
for ($in = $b; $in < $inputLength; ++$out) {
$oldi = $i;
$w = 1;
for ($k = self::BASE;; $k += self::BASE) {
if ($in >= $inputLength) {
throw new \Exception('Invalid input');
}
$digit = self::$basicToDigit[$bytes[$in++] & 0xff];
if ($digit < 0) {
throw new \Exception('Invalid input');
}
if ($digit > intdiv(self::MAX_INT - $i, $w)) {
throw new \Exception('Integer overflow');
}
$i += $digit * $w;
if ($k <= $bias) {
$t = self::TMIN;
} elseif ($k >= $bias + self::TMAX) {
$t = self::TMAX;
} else {
$t = $k - $bias;
}
if ($digit < $t) {
break;
}
$baseMinusT = self::BASE - $t;
if ($w > intdiv(self::MAX_INT, $baseMinusT)) {
throw new \Exception('Integer overflow');
}
$w *= $baseMinusT;
}
$outPlusOne = $out + 1;
$bias = self::adaptBias($i - $oldi, $outPlusOne, 0 === $oldi);
if (intdiv($i, $outPlusOne) > self::MAX_INT - $n) {
throw new \Exception('Integer overflow');
}
$n += intdiv($i, $outPlusOne);
$i %= $outPlusOne;
array_splice($output, $i++, 0, [mb_chr($n, 'utf-8')]);
}
return implode('', $output);
}
private static function punycodeEncode($input)
{
$n = self::INITIAL_N;
$delta = 0;
$out = 0;
$bias = self::INITIAL_BIAS;
$inputLength = 0;
$output = '';
$iter = self::utf8Decode($input);
foreach ($iter as $codePoint) {
++$inputLength;
if ($codePoint < 0x80) {
$output .= \chr($codePoint);
++$out;
}
}
$h = $out;
$b = $out;
if ($b > 0) {
$output .= self::DELIMITER;
++$out;
}
while ($h < $inputLength) {
$m = self::MAX_INT;
foreach ($iter as $codePoint) {
if ($codePoint >= $n && $codePoint < $m) {
$m = $codePoint;
}
}
if ($m - $n > intdiv(self::MAX_INT - $delta, $h + 1)) {
throw new \Exception('Integer overflow');
}
$delta += ($m - $n) * ($h + 1);
$n = $m;
foreach ($iter as $codePoint) {
if ($codePoint < $n && 0 === ++$delta) {
throw new \Exception('Integer overflow');
}
if ($codePoint === $n) {
$q = $delta;
for ($k = self::BASE;; $k += self::BASE) {
if ($k <= $bias) {
$t = self::TMIN;
} elseif ($k >= $bias + self::TMAX) {
$t = self::TMAX;
} else {
$t = $k - $bias;
}
if ($q < $t) {
break;
}
$qMinusT = $q - $t;
$baseMinusT = self::BASE - $t;
$output .= self::encodeDigit($t + $qMinusT % $baseMinusT, \false);
++$out;
$q = intdiv($qMinusT, $baseMinusT);
}
$output .= self::encodeDigit($q, \false);
++$out;
$bias = self::adaptBias($delta, $h + 1, $h === $b);
$delta = 0;
++$h;
}
}
++$delta;
++$n;
}
return $output;
}
private static function adaptBias($delta, $numPoints, $firstTime)
{
$delta = $firstTime ? intdiv($delta, self::DAMP) : $delta >> 1;
$delta += intdiv($delta, $numPoints);
$k = 0;
while ($delta > (self::BASE - self::TMIN) * self::TMAX >> 1) {
$delta = intdiv($delta, self::BASE - self::TMIN);
$k += self::BASE;
}
return $k + intdiv((self::BASE - self::TMIN + 1) * $delta, $delta + self::SKEW);
}
private static function encodeDigit($d, $flag)
{
return \chr($d + 22 + 75 * ($d < 26 ? 1 : 0) - (($flag ? 1 : 0) << 5));
}
private static function utf8Decode($input)
{
$bytesSeen = 0;
$bytesNeeded = 0;
$lowerBoundary = 0x80;
$upperBoundary = 0xbf;
$codePoint = 0;
$codePoints = [];
$length = \strlen($input);
for ($i = 0; $i < $length; ++$i) {
$byte = \ord($input[$i]);
if (0 === $bytesNeeded) {
if ($byte >= 0x0 && $byte <= 0x7f) {
$codePoints[] = $byte;
continue;
}
if ($byte >= 0xc2 && $byte <= 0xdf) {
$bytesNeeded = 1;
$codePoint = $byte & 0x1f;
} elseif ($byte >= 0xe0 && $byte <= 0xef) {
if (0xe0 === $byte) {
$lowerBoundary = 0xa0;
} elseif (0xed === $byte) {
$upperBoundary = 0x9f;
}
$bytesNeeded = 2;
$codePoint = $byte & 0xf;
} elseif ($byte >= 0xf0 && $byte <= 0xf4) {
if (0xf0 === $byte) {
$lowerBoundary = 0x90;
} elseif (0xf4 === $byte) {
$upperBoundary = 0x8f;
}
$bytesNeeded = 3;
$codePoint = $byte & 0x7;
} else {
$codePoints[] = 0xfffd;
}
continue;
}
if ($byte < $lowerBoundary || $byte > $upperBoundary) {
$codePoint = 0;
$bytesNeeded = 0;
$bytesSeen = 0;
$lowerBoundary = 0x80;
$upperBoundary = 0xbf;
--$i;
$codePoints[] = 0xfffd;
continue;
}
$lowerBoundary = 0x80;
$upperBoundary = 0xbf;
$codePoint = $codePoint << 6 | $byte & 0x3f;
if (++$bytesSeen !== $bytesNeeded) {
continue;
}
$codePoints[] = $codePoint;
$codePoint = 0;
$bytesNeeded = 0;
$bytesSeen = 0;
}
if (0 !== $bytesNeeded) {
$codePoints[] = 0xfffd;
}
return $codePoints;
}
private static function lookupCodePointStatus($codePoint, $useSTD3ASCIIRules)
{
if (!self::$mappingTableLoaded) {
self::$mappingTableLoaded = \true;
self::$mapped = require __DIR__ . '/Resources/unidata/mapped.php';
self::$ignored = require __DIR__ . '/Resources/unidata/ignored.php';
self::$deviation = require __DIR__ . '/Resources/unidata/deviation.php';
self::$disallowed = require __DIR__ . '/Resources/unidata/disallowed.php';
self::$disallowed_STD3_mapped = require __DIR__ . '/Resources/unidata/disallowed_STD3_mapped.php';
self::$disallowed_STD3_valid = require __DIR__ . '/Resources/unidata/disallowed_STD3_valid.php';
}
if (isset(self::$mapped[$codePoint])) {
return ['status' => 'mapped', 'mapping' => self::$mapped[$codePoint]];
}
if (isset(self::$ignored[$codePoint])) {
return ['status' => 'ignored'];
}
if (isset(self::$deviation[$codePoint])) {
return ['status' => 'deviation', 'mapping' => self::$deviation[$codePoint]];
}
if (isset(self::$disallowed[$codePoint]) || DisallowedRanges::inRange($codePoint)) {
return ['status' => 'disallowed'];
}
$isDisallowedMapped = isset(self::$disallowed_STD3_mapped[$codePoint]);
if ($isDisallowedMapped || isset(self::$disallowed_STD3_valid[$codePoint])) {
$status = 'disallowed';
if (!$useSTD3ASCIIRules) {
$status = $isDisallowedMapped ? 'mapped' : 'valid';
}
if ($isDisallowedMapped) {
return ['status' => $status, 'mapping' => self::$disallowed_STD3_mapped[$codePoint]];
}
return ['status' => $status];
}
return ['status' => 'valid'];
}
}
