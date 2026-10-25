<?php
namespace MailPoetVendor\Symfony\Component\Validator\Constraints;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Symfony\Component\Validator\Constraint;
use MailPoetVendor\Symfony\Component\Validator\ConstraintValidator;
use MailPoetVendor\Symfony\Component\Validator\Exception\UnexpectedTypeException;
class CardSchemeValidator extends ConstraintValidator
{
protected $schemes = [
CardScheme::AMEX => ['/^3[47][0-9]{13}$/D'],
CardScheme::CHINA_UNIONPAY => ['/^62[0-9]{14,17}$/D'],
CardScheme::DINERS => ['/^3(?:0[0-5]|[68][0-9])[0-9]{11}$/D'],
CardScheme::DISCOVER => ['/^6011[0-9]{12}$/D', '/^64[4-9][0-9]{13}$/D', '/^65[0-9]{14}$/D', '/^622(12[6-9]|1[3-9][0-9]|[2-8][0-9][0-9]|91[0-9]|92[0-5])[0-9]{10}$/D'],
CardScheme::INSTAPAYMENT => ['/^63[7-9][0-9]{13}$/D'],
CardScheme::JCB => ['/^(?:2131|1800|35[0-9]{3})[0-9]{11}$/D'],
CardScheme::LASER => ['/^(6304|670[69]|6771)[0-9]{12,15}$/D'],
CardScheme::MAESTRO => ['/^(6759[0-9]{2})[0-9]{6,13}$/D', '/^(50[0-9]{4})[0-9]{6,13}$/D', '/^5[6-9][0-9]{10,17}$/D', '/^6[0-9]{11,18}$/D'],
CardScheme::MASTERCARD => ['/^5[1-5][0-9]{14}$/D', '/^2(22[1-9][0-9]{12}|2[3-9][0-9]{13}|[3-6][0-9]{14}|7[0-1][0-9]{13}|720[0-9]{12})$/D'],
CardScheme::MIR => ['/^220[0-4][0-9]{12,15}$/D'],
CardScheme::UATP => ['/^1[0-9]{14}$/D'],
CardScheme::VISA => ['/^4([0-9]{12}|[0-9]{15}|[0-9]{18})$/D'],
];
public function validate($value, Constraint $constraint)
{
if (!$constraint instanceof CardScheme) {
throw new UnexpectedTypeException($constraint, CardScheme::class);
}
if (null === $value || '' === $value) {
return;
}
if (!is_numeric($value)) {
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(CardScheme::NOT_NUMERIC_ERROR)->addViolation();
return;
}
$schemes = array_flip((array) $constraint->schemes);
$schemeRegexes = array_intersect_key($this->schemes, $schemes);
foreach ($schemeRegexes as $regexes) {
foreach ($regexes as $regex) {
if (preg_match($regex, $value)) {
return;
}
}
}
$this->context->buildViolation($constraint->message)->setParameter('{{ value }}', $this->formatValue($value))->setCode(CardScheme::INVALID_FORMAT_ERROR)->addViolation();
}
}
