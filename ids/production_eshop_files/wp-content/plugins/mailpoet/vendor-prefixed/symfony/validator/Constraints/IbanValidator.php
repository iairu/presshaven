<?php
namespace MailPoetVendor\Symfony\Component\Validator\Constraints;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Symfony\Component\Validator\Constraint;
use MailPoetVendor\Symfony\Component\Validator\ConstraintValidator;
use MailPoetVendor\Symfony\Component\Validator\Exception\UnexpectedTypeException;
use MailPoetVendor\Symfony\Component\Validator\Exception\UnexpectedValueException;
class IbanValidator extends ConstraintValidator
{
private const FORMATS = [
'AD' => 'AD\d{2}\d{4}\d{4}[\dA-Z]{12}',
'AE' => 'AE\d{2}\d{3}\d{16}',
'AL' => 'AL\d{2}\d{8}[\dA-Z]{16}',
'AO' => 'AO\d{2}\d{21}',
'AT' => 'AT\d{2}\d{5}\d{11}',
'AX' => 'FI\d{2}\d{3}\d{11}',
'AZ' => 'AZ\d{2}[A-Z]{4}[\dA-Z]{20}',
'BA' => 'BA\d{2}\d{3}\d{3}\d{8}\d{2}',
'BE' => 'BE\d{2}\d{3}\d{7}\d{2}',
'BF' => 'BF\d{2}[\dA-Z]{2}\d{22}',
'BG' => 'BG\d{2}[A-Z]{4}\d{4}\d{2}[\dA-Z]{8}',
'BH' => 'BH\d{2}[A-Z]{4}[\dA-Z]{14}',
'BI' => 'BI\d{2}\d{5}\d{5}\d{11}\d{2}',
'BJ' => 'BJ\d{2}[\dA-Z]{2}\d{22}',
'BL' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'BR' => 'BR\d{2}\d{8}\d{5}\d{10}[A-Z]{1}[\dA-Z]{1}',
'BY' => 'BY\d{2}[\dA-Z]{4}\d{4}[\dA-Z]{16}',
'CF' => 'CF\d{2}\d{23}',
'CG' => 'CG\d{2}\d{23}',
'CH' => 'CH\d{2}\d{5}[\dA-Z]{12}',
'CI' => 'CI\d{2}[A-Z]{1}\d{23}',
'CM' => 'CM\d{2}\d{23}',
'CR' => 'CR\d{2}\d{4}\d{14}',
'CV' => 'CV\d{2}\d{21}',
'CY' => 'CY\d{2}\d{3}\d{5}[\dA-Z]{16}',
'CZ' => 'CZ\d{2}\d{4}\d{6}\d{10}',
'DE' => 'DE\d{2}\d{8}\d{10}',
'DJ' => 'DJ\d{2}\d{5}\d{5}\d{11}\d{2}',
'DK' => 'DK\d{2}\d{4}\d{9}\d{1}',
'DO' => 'DO\d{2}[\dA-Z]{4}\d{20}',
'DZ' => 'DZ\d{2}\d{22}',
'EE' => 'EE\d{2}\d{2}\d{2}\d{11}\d{1}',
'EG' => 'EG\d{2}\d{4}\d{4}\d{17}',
'ES' => 'ES\d{2}\d{4}\d{4}\d{1}\d{1}\d{10}',
'FI' => 'FI\d{2}\d{3}\d{11}',
'FK' => 'FK\d{2}[A-Z]{2}\d{12}',
'FO' => 'FO\d{2}\d{4}\d{9}\d{1}',
'FR' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'GA' => 'GA\d{2}\d{23}',
'GB' => 'GB\d{2}[A-Z]{4}\d{6}\d{8}',
'GE' => 'GE\d{2}[A-Z]{2}\d{16}',
'GF' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'GG' => 'GB\d{2}[A-Z]{4}\d{6}\d{8}',
'GI' => 'GI\d{2}[A-Z]{4}[\dA-Z]{15}',
'GL' => 'GL\d{2}\d{4}\d{9}\d{1}',
'GP' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'GQ' => 'GQ\d{2}\d{23}',
'GR' => 'GR\d{2}\d{3}\d{4}[\dA-Z]{16}',
'GT' => 'GT\d{2}[\dA-Z]{4}[\dA-Z]{20}',
'GW' => 'GW\d{2}[\dA-Z]{2}\d{19}',
'HN' => 'HN\d{2}[A-Z]{4}\d{20}',
'HR' => 'HR\d{2}\d{7}\d{10}',
'HU' => 'HU\d{2}\d{3}\d{4}\d{1}\d{15}\d{1}',
'IE' => 'IE\d{2}[A-Z]{4}\d{6}\d{8}',
'IL' => 'IL\d{2}\d{3}\d{3}\d{13}',
'IM' => 'GB\d{2}[A-Z]{4}\d{6}\d{8}',
'IQ' => 'IQ\d{2}[A-Z]{4}\d{3}\d{12}',
'IR' => 'IR\d{2}\d{22}',
'IS' => 'IS\d{2}\d{4}\d{2}\d{6}\d{10}',
'IT' => 'IT\d{2}[A-Z]{1}\d{5}\d{5}[\dA-Z]{12}',
'JE' => 'GB\d{2}[A-Z]{4}\d{6}\d{8}',
'JO' => 'JO\d{2}[A-Z]{4}\d{4}[\dA-Z]{18}',
'KM' => 'KM\d{2}\d{23}',
'KW' => 'KW\d{2}[A-Z]{4}[\dA-Z]{22}',
'KZ' => 'KZ\d{2}\d{3}[\dA-Z]{13}',
'LB' => 'LB\d{2}\d{4}[\dA-Z]{20}',
'LC' => 'LC\d{2}[A-Z]{4}[\dA-Z]{24}',
'LI' => 'LI\d{2}\d{5}[\dA-Z]{12}',
'LT' => 'LT\d{2}\d{5}\d{11}',
'LU' => 'LU\d{2}\d{3}[\dA-Z]{13}',
'LV' => 'LV\d{2}[A-Z]{4}[\dA-Z]{13}',
'LY' => 'LY\d{2}\d{3}\d{3}\d{15}',
'MA' => 'MA\d{2}\d{24}',
'MC' => 'MC\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'MD' => 'MD\d{2}[\dA-Z]{2}[\dA-Z]{18}',
'ME' => 'ME\d{2}\d{3}\d{13}\d{2}',
'MF' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'MG' => 'MG\d{2}\d{23}',
'MK' => 'MK\d{2}\d{3}[\dA-Z]{10}\d{2}',
'ML' => 'ML\d{2}[\dA-Z]{2}\d{22}',
'MN' => 'MN\d{2}\d{4}\d{12}',
'MQ' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'MR' => 'MR\d{2}\d{5}\d{5}\d{11}\d{2}',
'MT' => 'MT\d{2}[A-Z]{4}\d{5}[\dA-Z]{18}',
'MU' => 'MU\d{2}[A-Z]{4}\d{2}\d{2}\d{12}\d{3}[A-Z]{3}',
'MZ' => 'MZ\d{2}\d{21}',
'NC' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'NE' => 'NE\d{2}[A-Z]{2}\d{22}',
'NI' => 'NI\d{2}[A-Z]{4}\d{24}',
'NL' => 'NL\d{2}[A-Z]{4}\d{10}',
'NO' => 'NO\d{2}\d{4}\d{6}\d{1}',
'OM' => 'OM\d{2}\d{3}[\dA-Z]{16}',
'PF' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'PK' => 'PK\d{2}[A-Z]{4}[\dA-Z]{16}',
'PL' => 'PL\d{2}\d{8}\d{16}',
'PM' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'PS' => 'PS\d{2}[A-Z]{4}[\dA-Z]{21}',
'PT' => 'PT\d{2}\d{4}\d{4}\d{11}\d{2}',
'QA' => 'QA\d{2}[A-Z]{4}[\dA-Z]{21}',
'RE' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'RO' => 'RO\d{2}[A-Z]{4}[\dA-Z]{16}',
'RS' => 'RS\d{2}\d{3}\d{13}\d{2}',
'RU' => 'RU\d{2}\d{9}\d{5}[\dA-Z]{15}',
'SA' => 'SA\d{2}\d{2}[\dA-Z]{18}',
'SC' => 'SC\d{2}[A-Z]{4}\d{2}\d{2}\d{16}[A-Z]{3}',
'SD' => 'SD\d{2}\d{2}\d{12}',
'SE' => 'SE\d{2}\d{3}\d{16}\d{1}',
'SI' => 'SI\d{2}\d{5}\d{8}\d{2}',
'SK' => 'SK\d{2}\d{4}\d{6}\d{10}',
'SM' => 'SM\d{2}[A-Z]{1}\d{5}\d{5}[\dA-Z]{12}',
'SN' => 'SN\d{2}[A-Z]{2}\d{22}',
'SO' => 'SO\d{2}\d{4}\d{3}\d{12}',
'ST' => 'ST\d{2}\d{4}\d{4}\d{11}\d{2}',
'SV' => 'SV\d{2}[A-Z]{4}\d{20}',
'TD' => 'TD\d{2}\d{23}',
'TF' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'TG' => 'TG\d{2}[A-Z]{2}\d{22}',
'TL' => 'TL\d{2}\d{3}\d{14}\d{2}',
'TN' => 'TN\d{2}\d{2}\d{3}\d{13}\d{2}',
'TR' => 'TR\d{2}\d{5}\d{1}[\dA-Z]{16}',
'UA' => 'UA\d{2}\d{6}[\dA-Z]{19}',
'VA' => 'VA\d{2}\d{3}\d{15}',
'VG' => 'VG\d{2}[A-Z]{4}\d{16}',
'WF' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
'XK' => 'XK\d{2}\d{4}\d{10}\d{2}',
'YE' => 'YE\d{2}[A-Z]{4}\d{4}[\dA-Z]{18}',
'YT' => 'FR\d{2}\d{5}\d{5}[\dA-Z]{11}\d{2}',
];
public function validate($value, Constraint $constraint)
{
if (!$constraint instanceof Iban) {
throw new UnexpectedTypeException($constraint, Iban::class);
}
if (null === $value || '' === $value) {
return;
}
if (!\is_scalar($value) && !(\is_object($value) && method_exists($value, '__toString'))) {
throw new UnexpectedValueException($value, 'string');
}
$value = (string) $value;
$canonicalized = str_replace(' ', '', strtoupper($value));
if (!ctype_alnum($canonicalized)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::INVALID_CHARACTERS_ERROR)->addViolation();
return;
}
$countryCode = substr($canonicalized, 0, 2);
if (!ctype_alpha($countryCode)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::INVALID_COUNTRY_CODE_ERROR)->addViolation();
return;
}
if (!\array_key_exists($countryCode, self::FORMATS)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::NOT_SUPPORTED_COUNTRY_CODE_ERROR)->addViolation();
return;
}
if (!preg_match('/^' . self::FORMATS[$countryCode] . '$/', $canonicalized)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::INVALID_FORMAT_ERROR)->addViolation();
return;
}
$checkDigits = (int) substr($canonicalized, 2, 2);
if ($checkDigits < 2 || $checkDigits > 98) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::CHECKSUM_FAILED_ERROR)->addViolation();
return;
}
$canonicalized = substr($canonicalized, 4) . substr($canonicalized, 0, 4);
$checkSum = self::toBigInt($canonicalized);
if (1 !== self::bigModulo97($checkSum)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(Iban::CHECKSUM_FAILED_ERROR)->addViolation();
}
}
private static function toBigInt(string $string): string
{
$chars = str_split($string);
$bigInt = '';
foreach ($chars as $char) {
if (ctype_upper($char)) {
$bigInt .= \ord($char) - 55;
continue;
}
$bigInt .= $char;
}
return $bigInt;
}
private static function bigModulo97(string $bigInt): int
{
$parts = str_split($bigInt, 7);
$rest = 0;
foreach ($parts as $part) {
$rest = ($rest . $part) % 97;
}
return $rest;
}
}
