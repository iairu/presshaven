<?php
namespace WOOCS\Rates\Aggregators;

require_once WOOCS_PATH . 'classes/Rates/Aggregators/RateProvider.php';

/**
 * PulseverityRateProvider
 *
 * Crypto currencies only: Pulse Verity publishes crypto/USD prices,
 * so this source works only when the store base currency is USD.
 * Every store uses its own free API key (Bearer token, starts with pidx_).
 */
class PulseverityRateProvider extends RateProvider {

	const API_URL = 'https://mcp.thepulse.markets/api/index/v1/price?symbol=%s';

	// ISO 4217 codes plus a few unofficial and outdated ones that WooCommerce and FOX know
	const FIAT_CODES = 'AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL BSD BTN BWP BYN BYR BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GGP GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG HUF IDR ILS IMP INR IQD IRR IRT ISK JEP JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LTL LVL LYD MAD MDL MGA MKD MMK MNT MOP MRO MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PRB PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SLL SOS SRD SSP STD STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD USN UYI UYU UYW UZS VED VEF VES VND VUV WST XAF XAG XAU XCD XCG XOF XPD XPF XPT YER ZAR ZMK ZMW ZWG ZWL';

	public function __construct( string $base, string $key = '' ) {
		parent::__construct( $base, $key );
		$this->name = \esc_html__( 'Pulse Verity', 'woocommerce-currency-switcher' );
	}

	public function getRate( string $to ): float {
		$this->resetError();

		// Only crypto/USD pairs exist on the Pulse Verity side
		if ( 'USD' !== strtoupper( $this->base ) ) {
			$this->setError( \esc_html__( 'Pulse Verity works only with USD as the base currency', 'woocommerce-currency-switcher' ) );
			return -1;
		}

		if ( ! $this->key ) {
			$this->setError( \esc_html__( 'This aggregator requires a license code', 'woocommerce-currency-switcher' ) );
			return -1;
		}

		$to = strtoupper( trim( $to ) );
		if ( 'USD' === $to ) {
			return 1;
		}

		// Pulse Verity treats any symbol as a crypto ticker, so a fiat code like CAD
		// would return the price of an unrelated token. Fiat rates are never requested.
		if ( $this->isFiat( $to ) ) {
			// translators: %s is a currency code.
			$this->setError( sprintf( \esc_html__( 'Pulse Verity provides crypto currencies only, %s is not a crypto currency', 'woocommerce-currency-switcher' ), $to ) );
			return -1;
		}

		return parent::getRate( $to );
	}

	private function isFiat( string $code ): bool {
		static $fiat = null;
		if ( null === $fiat ) {
			// The list is hardcoded on purpose: crypto payment plugins add their coins to the WooCommerce currency list
			$fiat = (array) \apply_filters( 'woocs_pulseverity_fiat_codes', explode( ' ', self::FIAT_CODES ) );
		}
		return in_array( $code, $fiat, true );
	}

	protected function getApiUrl( string $to ): string {
		return sprintf( self::API_URL, rawurlencode( $to ) );
	}

	// The base doRequest() cannot send headers, the key goes in the Authorization header
	protected function doRequest( string $url ) {
		$args = array(
			'timeout' => 15,
			'headers' => array(
				'Accept'        => 'application/json',
				'Authorization' => 'Bearer ' . $this->key,
			),
		);

		$response = \wp_remote_get( $url, $args );

		if ( \is_wp_error( $response ) ) {
			$this->setError( $response->get_error_message() );
			\error_log( '[WOOCS] Pulse Verity request error: ' . $response->get_error_message() );// phpcs:ignore WordPress.PHP.DevelopmentFunctions.error_log_error_log
			return array();
		}

		$code = (int) \wp_remote_retrieve_response_code( $response );
		$data = json_decode( \wp_remote_retrieve_body( $response ), true );

		// Non-2xx: 401 wrong key, 403 plan restriction, 429 per-minute or monthly limit
		if ( $code < 200 || $code >= 300 ) {
			$reason = 'HTTP ' . $code;
			if ( is_array( $data ) ) {
				if ( isset( $data['error']['code'] ) && is_string( $data['error']['code'] ) ) {
					$reason = $data['error']['code'];
				} elseif ( isset( $data['error'] ) && is_string( $data['error'] ) ) {
					$reason = $data['error'];
				} elseif ( isset( $data['message'] ) && is_string( $data['message'] ) ) {
					$reason = $data['message'];
				}
			}
			// translators: %s is an error message or value.
			$this->setError( sprintf( \esc_html__( 'Aggregator Error:%s', 'woocommerce-currency-switcher' ), \sanitize_text_field( $reason ) ) );
			return array();
		}

		if ( ! is_array( $data ) ) {
			$this->setError( 'Invalid JSON response' );
			return array();
		}

		return $data;
	}

	protected function parseResponse( $data, string $to ): float {
		// An unavailable price comes back as an explicit error, never as zero, but guard anyway
		if ( ! is_array( $data ) || ! isset( $data['price'] ) || ! is_numeric( $data['price'] ) || (float) $data['price'] <= 0 ) {
			if ( ! $this->getLastError() ) {
				// translators: %s is an error message or value.
				$this->setError( sprintf( \esc_html__( 'no data for %s', 'woocommerce-currency-switcher' ), $to ) );
			}
			return -1;
		}

		// Pulse Verity returns USD per 1 coin, FOX needs coins per 1 USD
		return 1 / (float) $data['price'];
	}
}