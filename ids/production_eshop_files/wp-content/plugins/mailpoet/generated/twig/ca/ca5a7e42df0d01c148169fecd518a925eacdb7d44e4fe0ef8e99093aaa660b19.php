<?php

if (!defined('ABSPATH')) exit;


use MailPoetVendor\Twig\Environment;
use MailPoetVendor\Twig\Error\LoaderError;
use MailPoetVendor\Twig\Error\RuntimeError;
use MailPoetVendor\Twig\Extension\CoreExtension;
use MailPoetVendor\Twig\Extension\SandboxExtension;
use MailPoetVendor\Twig\Markup;
use MailPoetVendor\Twig\Sandbox\SecurityError;
use MailPoetVendor\Twig\Sandbox\SecurityNotAllowedTagError;
use MailPoetVendor\Twig\Sandbox\SecurityNotAllowedFilterError;
use MailPoetVendor\Twig\Sandbox\SecurityNotAllowedFunctionError;
use MailPoetVendor\Twig\Source;
use MailPoetVendor\Twig\Template;

/* emails/statsNotificationAutomatedEmails.html */
class __TwigTemplate_2bbd0548d5462e9781dcc2649091521a405c5b3b1847f123d5fb51dce2ee5625 extends Template
{
    private $source;
    private $macros = [];

    public function __construct(Environment $env)
    {
        parent::__construct($env);

        $this->source = $this->getSourceContext();

        $this->blocks = [
            'content' => [$this, 'block_content'],
        ];
    }

    protected function doGetParent(array $context)
    {
        // line 1
        return "emails/statsNotificationLayout.html";
    }

    protected function doDisplay(array $context, array $blocks = [])
    {
        $macros = $this->macros;
        $this->parent = $this->loadTemplate("emails/statsNotificationLayout.html", "emails/statsNotificationAutomatedEmails.html", 1);
        yield from $this->parent->unwrap()->yield($context, array_merge($this->blocks, $blocks));
    }

    // line 3
    public function block_content($context, array $blocks = [])
    {
        $macros = $this->macros;
        // line 4
        yield "<tr>
  <td class=\"mailpoet_content\" align=\"center\" style=\"border-collapse:collapse\">
    <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;border-collapse:collapse\">
      <tbody>
      <tr>
        <td style=\"padding-left:0;padding-right:0;border-collapse:collapse\">
          <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" class=\"mailpoet_cols-one\" style=\"border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0;border-collapse:collapse\">
            <tbody>
            <tr>
              <td class=\"mailpoet_spacer\" height=\"36\" valign=\"top\" style=\"border-collapse:collapse\"></td>
            </tr>
            <tr>
              <td class=\"mailpoet_image mailpoet_padded_vertical mailpoet_padded_side\" align=\"center\" valign=\"top\" style=\"border-collapse:collapse;padding-bottom:20px;padding-left:20px;padding-right:20px\">
                <img src=\"";
        // line 17
        yield $this->extensions['MailPoet\Twig\Assets']->generateCdnUrl("logo-orange-400x122.png");
        yield "\" width=\"80\" alt=\"new_logo_orange\" style=\"height:auto;max-width:100%;-ms-interpolation-mode:bicubic;border:0;display:block;outline:none;text-align:center\" />
              </td>
            </tr>
            <tr>
              <td class=\"mailpoet_spacer\" height=\"26\" valign=\"top\" style=\"border-collapse:collapse\"></td>
            </tr>
            <tr>
              <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"word-break:break-word;word-wrap:break-word;padding-top:0;border-collapse:collapse;padding-bottom:20px;padding-left:20px;padding-right:20px\">
                <h1 style=\"text-align:center;padding:0;font-style:normal;font-weight:normal;margin:0 0 12px;color:#111111;font-family:'Trebuchet MS','Lucida Grande','Lucida Sans Unicode','Lucida Sans',Tahoma,sans-serif;font-size:40px;line-height:64px\">
                  <strong>";
        // line 26
        yield $this->extensions['MailPoet\Twig\I18n']->translate("Your monthly stats are in!");
        yield "</strong>
                </h1>
              </td>
            </tr>
            <tr>
              <td class=\"mailpoet_spacer\" height=\"55\" valign=\"top\" style=\"border-collapse:collapse\"></td>
            </tr>
            </tbody>
          </table>
        </td>
      </tr>
      </tbody>
    </table>
  </td>
</tr>

";
        // line 42
        $context['_parent'] = $context;
        $context['_seq'] = CoreExtension::ensureTraversable(($context["newsletters"] ?? null));
        foreach ($context['_seq'] as $context["_key"] => $context["newsletter"]) {
            // line 43
            yield "  <tr>
    <td class=\"mailpoet_content\" align=\"center\" style=\"border-collapse:collapse\">
      <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
        <tbody>
        <tr>
          <td style=\"border-collapse:collapse;padding-left:0;padding-right:0\">
            <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" class=\"mailpoet_cols-one\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
              <tbody>
              <tr>
                <td class=\"mailpoet_divider\" valign=\"top\" style=\"border-collapse:collapse;padding:29.5px 20px 29.5px 20px\">
                  <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
                    <tr>
                      <td class=\"mailpoet_divider-cell\" style=\"border-collapse:collapse;border-top-width:1px;border-top-style:solid;border-top-color:#e8e8e8\">
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              <tr>
                <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                  <h2 class=\"title\" style=\"margin:0 0 7.8px;color:#222222;font-family:lato,'helvetica neue',helvetica,arial,sans-serif;font-size:26px;line-height:31.2px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                    <strong>
                      <a href=\"";
            // line 65
            yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "linkStats", [], "any", false, false, false, 65), "html", null, true);
            yield "\" style=\"color:#0074a2;text-decoration:underline\">
                        ";
            // line 66
            yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "subject", [], "any", false, false, false, 66), "html", null, true);
            yield "
                      </a>
                    </strong>
                  </h2>
                </td>
              </tr>
              <tr>
                <td class=\"mailpoet_spacer\" height=\"28\" valign=\"top\" style=\"border-collapse:collapse\"></td>
              </tr>
              </tbody>
            </table>
          </td>
        </tr>
        </tbody>
      </table>
    </td>
  </tr>

  <tr>
    <td class=\"mailpoet_content-cols-two\" align=\"left\" style=\"border-collapse:collapse\">
      <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
        <tbody>
        <tr>
          <td align=\"center\" style=\"border-collapse:collapse;font-size:0\">
            <!--[if mso]>
            <table border=\"0\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">
              <tbody>
              <tr>
                <td width=\"330\" valign=\"top\">
            <![endif]-->
            <div style=\"display:inline-block; max-width:330px; vertical-align:top; width:100%;\">
              <table width=\"330\" class=\"mailpoet_cols-two\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" align=\"left\" style=\"border-collapse:collapse;width:100%;max-width:330px;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
                <tbody>
                <tr>
                  <td class=\"mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px\">
                    <div>
                      <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
                        <tr>
                          <td class=\"mailpoet_button-container\" style=\"border-collapse:collapse;text-align:center\">
                            <!--[if mso]>
                            <v:roundrect xmlns:v=\"urn:schemas-microsoft-com:vml\" xmlns:w=\"urn:schemas-microsoft-com:office:word\"
                                         href=\"";
            // line 107
            yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "linkStats", [], "any", false, false, false, 107), "html", null, true);
            yield "\"
                                         style=\"height:20px;
                             width:50px;
                             v-text-anchor:middle;\"
                                         arcsize=\"15%\"
                                         strokeweight=\"0px\"
                                         strokecolor=\"#0074a2\"
                                         fillcolor=\"";
            // line 114
            yield $this->extensions['MailPoet\Twig\Functions']->statsColor(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 114));
            yield "\">
                              <w:anchorlock/>
                              <center style=\"color:#ffffff; font-family:Arial; font-size:10px; font-weight:bold;\">
                                ";
            // line 117
            yield $this->extensions['MailPoet\Twig\Functions']->clickedStatsText(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 117));
            yield "
                              </center>
                            </v:roundrect>
                            <![endif]-->
                            <a class=\"mailpoet_button\" href=\"";
            // line 121
            yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "linkStats", [], "any", false, false, false, 121), "html", null, true);
            yield "\" style=\"color:#ffffff;text-decoration:none !important;display:inline-block;-webkit-text-size-adjust:none;mso-hide:all;text-align:center;background-color:";
            yield $this->extensions['MailPoet\Twig\Functions']->statsColor(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 121));
            yield ";border-color:#0074a2;border-width:0px;border-radius:3px;border-style:solid;width:80px;line-height:20px;font-family:Arial, 'Helvetica Neue', Helvetica, sans-serif;font-size:10px;font-weight:normal\">
                              ";
            // line 122
            yield $this->extensions['MailPoet\Twig\Functions']->clickedStatsText(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 122));
            yield "
                            </a>
                          </td>
                        </tr>
                      </table>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                    <h3 style=\"margin:0 0 5.4px;color:#333333;font-family:'Courier New',Courier,'Lucida Sans Typewriter','Lucida Typewriter',monospace;font-size:18px;line-height:21.6px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                      <span style=\"color: ";
            // line 133
            yield $this->extensions['MailPoet\Twig\Functions']->statsColor(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 133));
            yield ";\">
                        <strong>
                          <span style=\"color: ";
            // line 135
            yield $this->extensions['MailPoet\Twig\Functions']->statsColor(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 135));
            yield ";\">";
            yield $this->extensions['MailPoet\Twig\Functions']->statsNumberFormatI18n(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "clicked", [], "any", false, false, false, 135));
            yield "%</span>
                        </strong>
                        <span style=\"color: #000000;\">
                          ";
            // line 138
            yield $this->extensions['MailPoet\Twig\I18n']->translate("clicked");
            yield "
                        </span>
                      </span>
                    </h3>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
            <!--[if mso]>
            </td>
            </tr>
            </tbody>
            </table>
            <![endif]-->
          </td>
        </tr>
        </tbody>
      </table>
    </td>
  </tr>

  <tr>
    <td class=\"mailpoet_content-cols-two\" align=\"left\" style=\"border-collapse:collapse\">
      <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
        <tbody>
        <tr>
          <td align=\"center\" style=\"border-collapse:collapse;font-size:0\">
            <!--[if mso]>
            <table border=\"0\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">
              <tbody>
              <tr>
                <td width=\"330\" valign=\"top\">
            <![endif]-->
            <div style=\"display:inline-block; max-width:330px; vertical-align:top; width:100%;\">
              <table width=\"330\" class=\"mailpoet_cols-two\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" align=\"left\" style=\"border-collapse:collapse;width:100%;max-width:330px;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
                <tbody>
                <tr>
                  <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                    <h3 style=\"margin:0 0 5.4px;color:#333333;font-family:'Courier New',Courier,'Lucida Sans Typewriter','Lucida Typewriter',monospace;font-size:18px;line-height:21.6px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                      <span>
                        <strong>";
            // line 179
            yield $this->extensions['MailPoet\Twig\Functions']->statsNumberFormatI18n(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "opened", [], "any", false, false, false, 179));
            yield "%</strong> ";
            yield $this->extensions['MailPoet\Twig\I18n']->translate("opened");
            yield "
                      </span>
                    </h3>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
            <!--[if mso]>
            </td>
            <td width=\"330\" valign=\"top\">
            <![endif]-->
            <div style=\"display:inline-block; max-width:330px; vertical-align:top; width:100%;\">
              <table width=\"330\" class=\"mailpoet_cols-two\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" align=\"left\" style=\"border-collapse:collapse;width:100%;max-width:330px;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
                <tbody>
                <tr>
                  <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                    <h3 style=\"margin:0 0 5.4px;color:#333333;font-family:'Courier New',Courier,'Lucida Sans Typewriter','Lucida Typewriter',monospace;font-size:18px;line-height:21.6px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                      <span>
                        <strong>";
            // line 198
            yield $this->extensions['MailPoet\Twig\Functions']->statsNumberFormatI18n(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "machineOpened", [], "any", false, false, false, 198));
            yield "%</strong> ";
            yield $this->extensions['MailPoet\Twig\I18n']->translate("machine-opened");
            yield "
                      </span>
                    </h3>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
            <!--[if mso]>
            </td>
            </tr>
            </tbody>
            </table>
            <![endif]-->
          </td>
        </tr>
        </tbody>
      </table>
    </td>
  </tr>

  <tr>
    <td class=\"mailpoet_content-cols-two\" align=\"left\" style=\"border-collapse:collapse\">
      <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0\">
        <tbody>
        <tr>
          <td align=\"center\" style=\"border-collapse:collapse;font-size:0\">
            <!--[if mso]>
            <table border=\"0\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\">
              <tbody>
              <tr>
                <td width=\"330\" valign=\"top\">
            <![endif]-->
            <div style=\"display:inline-block; max-width:330px; vertical-align:top; width:100%;\">
              <table width=\"330\" class=\"mailpoet_cols-two\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" align=\"left\" style=\"border-collapse:collapse;width:100%;max-width:330px;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
                <tbody>
                <tr>
                  <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                    <h3 style=\"margin:0 0 5.4px;color:#333333;font-family:'Courier New',Courier,'Lucida Sans Typewriter','Lucida Typewriter',monospace;font-size:18px;line-height:21.6px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                      <span>
                        <strong>";
            // line 238
            yield $this->extensions['MailPoet\Twig\Functions']->statsNumberFormatI18n(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "unsubscribed", [], "any", false, false, false, 238));
            yield "%</strong> ";
            yield $this->extensions['MailPoet\Twig\I18n']->translate("unsubscribed");
            yield "
                      </span>
                    </h3>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
            <!--[if mso]>
            </td>
            <td width=\"330\" valign=\"top\">
            <![endif]-->
            <div style=\"display:inline-block; max-width:330px; vertical-align:top; width:100%;\">
              <table width=\"330\" class=\"mailpoet_cols-two\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" align=\"left\" style=\"border-collapse:collapse;width:100%;max-width:330px;border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;table-layout:fixed;margin-left:auto;margin-right:auto;padding-left:0;padding-right:0\">
                <tbody>
                <tr>
                  <td class=\"mailpoet_text mailpoet_padded_vertical mailpoet_padded_side\" valign=\"top\" style=\"border-collapse:collapse;padding-top:10px;padding-bottom:10px;padding-left:20px;padding-right:20px;word-break:break-word;word-wrap:break-word\">
                    <h3 style=\"margin:0 0 5.4px;color:#333333;font-family:'Courier New',Courier,'Lucida Sans Typewriter','Lucida Typewriter',monospace;font-size:18px;line-height:21.6px;margin-bottom:0;text-align:center;padding:0;font-style:normal;font-weight:normal\">
                      <span>
                        <strong>";
            // line 257
            yield $this->extensions['MailPoet\Twig\Functions']->statsNumberFormatI18n(CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "bounced", [], "any", false, false, false, 257));
            yield "%</strong> ";
            yield $this->extensions['MailPoet\Twig\I18n']->translate("bounced");
            yield "
                      </span>
                    </h3>
                  </td>
                </tr>
                </tbody>
              </table>
            </div>
            <!--[if mso]>
            </td>
            </tr>
            </tbody>
            </table>
            <![endif]-->
          </td>
        </tr>
        </tbody>
      </table>
    </td>
  </tr>
  ";
            // line 277
            if ((CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "notTracked", [], "any", false, false, false, 277) > 0)) {
                // line 278
                yield "  <tr>
    <td class=\"mailpoet_content\" align=\"center\" style=\"border-collapse:collapse\">
      <table width=\"100%\" border=\"0\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-spacing:0;mso-table-lspace:0;mso-table-rspace:0;border-collapse:collapse\">
        <tbody>
        <tr>
          <td class=\"mailpoet_paragraph mailpoet_padded_side\" style=\"word-break:break-word;word-wrap:break-word;text-align:center;border-collapse:collapse;color:#7f7f7f;font-family:Arial,'Helvetica Neue',Helvetica,sans-serif;font-size:13px;line-height:20px;padding-left:20px;padding-right:20px;padding-bottom:10px\">
            ";
                // line 284
                if ((CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "trackedSent", [], "any", false, false, false, 284) > 0)) {
                    // line 285
                    yield "              ";
                    yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(MailPoetVendor\Twig\Extension\CoreExtension::replace($this->extensions['MailPoet\Twig\I18n']->pluralize("%1\$s of your recipients is not tracked, so open and click rates are based on the other %2\$s.", "%1\$s of your recipients are not tracked, so open and click rates are based on the other %2\$s.", CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "notTracked", [], "any", false, false, false, 285)), ["%1\$s" => CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "notTracked", [], "any", false, false, false, 285), "%2\$s" => CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "trackedSent", [], "any", false, false, false, 285)]), "html", null, true);
                    yield "
            ";
                } else {
                    // line 287
                    yield "              ";
                    yield $this->env->getRuntime('MailPoetVendor\Twig\Runtime\EscaperRuntime')->escape(MailPoetVendor\Twig\Extension\CoreExtension::replace($this->extensions['MailPoet\Twig\I18n']->pluralize("Your %1\$s recipient is not tracked, so open and click rates cannot be measured.", "None of your %1\$s recipients are tracked, so open and click rates cannot be measured.", CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "notTracked", [], "any", false, false, false, 287)), ["%1\$s" => CoreExtension::getAttribute($this->env, $this->source, $context["newsletter"], "notTracked", [], "any", false, false, false, 287)]), "html", null, true);
                    yield "
            ";
                }
                // line 289
                yield "          </td>
        </tr>
        </tbody>
      </table>
    </td>
  </tr>
  ";
            }
        }
        $_parent = $context['_parent'];
        unset($context['_seq'], $context['_iterated'], $context['_key'], $context['newsletter'], $context['_parent'], $context['loop']);
        $context = array_intersect_key($context, $_parent) + $_parent;
        // line 297
        yield "
<tr>
  <td class=\"mailpoet_spacer\" height=\"55\" valign=\"top\" style=\"border-collapse:collapse\"></td>
</tr>
";
        return; yield '';
    }

    /**
     * @codeCoverageIgnore
     */
    public function getTemplateName()
    {
        return "emails/statsNotificationAutomatedEmails.html";
    }

    /**
     * @codeCoverageIgnore
     */
    public function isTraitable()
    {
        return false;
    }

    /**
     * @codeCoverageIgnore
     */
    public function getDebugInfo()
    {
        return array (  428 => 297,  415 => 289,  409 => 287,  403 => 285,  401 => 284,  393 => 278,  391 => 277,  366 => 257,  342 => 238,  297 => 198,  273 => 179,  229 => 138,  221 => 135,  216 => 133,  202 => 122,  196 => 121,  189 => 117,  183 => 114,  173 => 107,  129 => 66,  125 => 65,  101 => 43,  97 => 42,  78 => 26,  66 => 17,  51 => 4,  47 => 3,  36 => 1,);
    }

    public function getSourceContext()
    {
        return new Source("", "emails/statsNotificationAutomatedEmails.html", "/home/circleci/mailpoet/mailpoet/views/emails/statsNotificationAutomatedEmails.html");
    }
}
