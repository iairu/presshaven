<?php
namespace MailPoetVendor\Symfony\Component\Validator\Constraints;
if (!defined('ABSPATH')) exit;
use MailPoetVendor\Symfony\Component\Validator\Constraint;
use MailPoetVendor\Symfony\Component\Validator\Exception\ConstraintDefinitionException;
abstract class Compound extends Composite
{
public $constraints = [];
public function __construct($options = null)
{
if (isset($options[$this->getCompositeOption()])) {
throw new ConstraintDefinitionException(sprintf('You can\'t redefine the "%s" option. Use the "%s::getConstraints()" method instead.', $this->getCompositeOption(), __CLASS__));
}
$this->constraints = $this->getConstraints($this->normalizeOptions($options));
parent::__construct($options);
}
final protected function getCompositeOption(): string
{
return 'constraints';
}
final public function validatedBy(): string
{
return CompoundValidator::class;
}
abstract protected function getConstraints(array $options): array;
}
