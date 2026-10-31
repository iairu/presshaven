#!/usr/local/bin/php
<?php
/**
 * production-firewall: the iptables ruleset of production_eshop's own network
 * namespace. Only NEW connections are filtered -- loopback and ESTABLISHED /
 * RELATED traffic always passes -- so a connection is allowed when it opens
 * only if a rule names its peer and port: inbound, only the edge may open a
 * connection to Apache; outbound, PHP may reach only what the rules list (the
 * database, the public internet on 443, ...). Everything else is dropped
 * (inbound) or rejected (outbound: fails fast instead of hanging PHP).
 *
 *   production-firewall boot           apply the saved ruleset (or the default)
 *   production-firewall apply --b64 X  validate, apply and save a ruleset
 *   production-firewall status         JSON: ruleset, resolved peers, counters
 *   production-firewall watch          re-resolve peers every 5 s, re-apply on
 *                                      change (the edge's IP changes whenever
 *                                      reverse_proxy is recreated)
 *   production-firewall default        print the image's default ruleset
 *
 * Needs CAP_NET_ADMIN (compose: cap_add NET_ADMIN). Started as root from the
 * production command, which then drops NET_ADMIN from Apache's bounding set,
 * so neither Apache nor PHP can change these rules. The dashboard's
 * Production Firewall page drives it through `docker compose exec`, which gets
 * the container's full capability set.
 *
 * Own chains only (PFW_IN, PFW_OUT, PFW_INET in the filter table), hooked
 * first into INPUT and OUTPUT, replaced atomically with iptables-restore
 * --noflush. The nat table is never touched: Docker's embedded DNS
 * (127.0.0.11) lives there, and reaches us over loopback.
 *
 * Ruleset document (version 1), validated identically by the dashboard
 * (dashboard/core/production_firewall.py):
 *   {version, enabled, inbound: [rule], outbound: [rule]}
 *   rule = {id, enabled, peer, proto, ports, label, layer?}
 *   peer  : a container / service name (resolved on every apply), an IPv4
 *           address or CIDR, "any", "local-subnets" (every subnet this
 *           container is attached to) or, outbound only, "internet" (anything
 *           outside the private / reserved ranges)
 *   proto : tcp | udp | tcp/udp
 *   ports : "80", "465,587", "8000-8100" (at most 15 ports, a range counts 2)
 *   layer : "default" | "db-proxy" -- the rule applies only in that honeypot
 *           layer ($PRODUCTION_FIREWALL_LAYER); absent = every layer
 */

const STATE_DIR = '/var/lib/production-firewall';
const STATE_FILE = STATE_DIR . '/ruleset.json';
const RUNTIME_FILE = '/run/production-firewall.json';
const DEFAULT_FILE = '/usr/local/share/production-firewall/default.json';
const WATCH_INTERVAL = 5;
const MAX_RULES = 64;
const MAX_PORTS = 15;
const PEER_KEYWORDS = ['any', 'internet', 'local-subnets'];
const LAYERS = ['default', 'db-proxy'];
// Not "internet": RFC 1918, loopback, link-local, CGNAT, "this network",
// multicast and reserved.
const NON_INTERNET = ['0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16',
	'172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '240.0.0.0/4'];

function fail( string $msg, int $code = 1 ): void {
	fwrite( STDERR, "production-firewall: $msg\n" );
	exit( $code );
}

function layer(): string {
	$l = getenv( 'PRODUCTION_FIREWALL_LAYER' );
	return in_array( $l, LAYERS, true ) ? $l : 'default';
}

/** Runs argv (no shell); returns [exit code, stdout, stderr]. */
function run( array $argv, ?string $stdin = null ): array {
	$p = proc_open( $argv, [ 0 => [ 'pipe', 'r' ], 1 => [ 'pipe', 'w' ], 2 => [ 'pipe', 'w' ] ], $pipes );
	if ( ! is_resource( $p ) ) {
		return [ 127, '', "cannot run {$argv[0]}" ];
	}
	if ( $stdin !== null ) {
		fwrite( $pipes[0], $stdin );
	}
	fclose( $pipes[0] );
	$out = stream_get_contents( $pipes[1] );
	$err = stream_get_contents( $pipes[2] );
	fclose( $pipes[1] );
	fclose( $pipes[2] );
	return [ proc_close( $p ), $out, $err ];
}

// -- validation ---------------------------------------------------------------

function valid_cidr( string $s ): bool {
	if ( ! preg_match( '#^(\d{1,3}(?:\.\d{1,3}){3})(?:/(\d{1,2}))?$#', $s, $m ) ) {
		return false;
	}
	return filter_var( $m[1], FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 ) !== false
		&& ( ! isset( $m[2] ) || (int) $m[2] <= 32 );
}

/** Canonical port list ("80,443", "8000:8100") or an error string prefixed "!". */
function parse_ports( $ports ): string {
	if ( ! is_string( $ports ) || trim( $ports ) === '' ) {
		return '!ports are required';
	}
	$out = [];
	$weight = 0;
	foreach ( explode( ',', str_replace( ' ', '', $ports ) ) as $part ) {
		if ( ! preg_match( '/^(\d{1,5})(?:-(\d{1,5}))?$/', $part, $m ) ) {
			return "!bad port \"$part\"";
		}
		$lo = (int) $m[1];
		$hi = isset( $m[2] ) ? (int) $m[2] : $lo;
		if ( $lo < 1 || $hi > 65535 || $lo > $hi ) {
			return "!bad port \"$part\"";
		}
		$out[] = $lo === $hi ? (string) $lo : "$lo:$hi";
		$weight += $lo === $hi ? 1 : 2;
	}
	if ( $weight > MAX_PORTS ) {
		return '!at most ' . MAX_PORTS . ' ports per rule (a range counts as two)';
	}
	return implode( ',', $out );
}

/** Returns a list of error strings; empty = valid. */
function validate( $doc ): array {
	if ( ! is_array( $doc ) ) {
		return [ 'ruleset must be a JSON object' ];
	}
	$errors = [];
	if ( ( $doc['version'] ?? null ) !== 1 ) {
		$errors[] = 'version must be 1';
	}
	if ( ! is_bool( $doc['enabled'] ?? null ) ) {
		$errors[] = 'enabled must be true or false';
	}
	foreach ( [ 'inbound', 'outbound' ] as $dir ) {
		$rules = $doc[ $dir ] ?? null;
		if ( ! is_array( $rules ) || ( $rules && array_keys( $rules ) !== range( 0, count( $rules ) - 1 ) ) ) {
			$errors[] = "$dir must be a list";
			continue;
		}
		if ( count( $rules ) > MAX_RULES ) {
			$errors[] = "$dir: at most " . MAX_RULES . ' rules';
		}
		$seen = [];
		foreach ( $rules as $i => $r ) {
			$where = "{$dir}[$i]";
			if ( ! is_array( $r ) ) {
				$errors[] = "$where: must be an object";
				continue;
			}
			$id = $r['id'] ?? '';
			if ( ! is_string( $id ) || ! preg_match( '/^[a-z0-9][a-z0-9-]{0,47}$/', $id ) ) {
				$errors[] = "$where: id must be 1-48 of a-z 0-9 -";
			} elseif ( isset( $seen[ $id ] ) ) {
				$errors[] = "$where: duplicate id $id";
			} else {
				$seen[ $id ] = true;
				$where = "$dir/$id";
			}
			if ( ! is_bool( $r['enabled'] ?? null ) ) {
				$errors[] = "$where: enabled must be true or false";
			}
			$peer = $r['peer'] ?? '';
			if ( ! is_string( $peer ) || ! ( in_array( $peer, PEER_KEYWORDS, true ) || valid_cidr( $peer )
					|| ( preg_match( '/^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$/', $peer ) && ! preg_match( '#^[\d./]+$#', $peer ) ) ) ) {
				$errors[] = "$where: peer must be a container name, an IPv4 address/CIDR, any, local-subnets or internet";
			} elseif ( $peer === 'internet' && $dir === 'inbound' ) {
				$errors[] = "$where: internet is outbound only (inbound traffic always comes through the edge)";
			}
			if ( ! in_array( $r['proto'] ?? '', [ 'tcp', 'udp', 'tcp/udp' ], true ) ) {
				$errors[] = "$where: proto must be tcp, udp or tcp/udp";
			}
			$ports = parse_ports( $r['ports'] ?? null );
			if ( $ports[0] === '!' ) {
				$errors[] = "$where: " . substr( $ports, 1 );
			}
			if ( ! is_string( $r['label'] ?? '' ) || strlen( $r['label'] ?? '' ) > 200 ) {
				$errors[] = "$where: label must be text of at most 200 characters";
			}
			if ( isset( $r['layer'] ) && ! in_array( $r['layer'], LAYERS, true ) ) {
				$errors[] = "$where: layer must be default or db-proxy";
			}
		}
	}
	return $errors;
}

// -- ruleset --------------------------------------------------------------------

function load_default(): array {
	$doc = json_decode( (string) @file_get_contents( DEFAULT_FILE ), true );
	if ( validate( $doc ) ) {
		fail( 'the image default ruleset ' . DEFAULT_FILE . ' is invalid' );
	}
	return $doc;
}

/** The saved ruleset, or the image default when there is none (or it is broken). */
function load_saved( ?string &$source = null ): array {
	$raw = @file_get_contents( STATE_FILE );
	if ( $raw !== false ) {
		$doc = json_decode( $raw, true );
		if ( ! validate( $doc ) ) {
			$source = 'saved';
			return $doc;
		}
		fwrite( STDERR, 'production-firewall: ' . STATE_FILE . " is invalid, using the default\n" );
	}
	$source = 'default';
	return load_default();
}

function save( array $doc ): void {
	if ( ! is_dir( STATE_DIR ) && ! mkdir( STATE_DIR, 0700, true ) ) {
		fail( 'cannot create ' . STATE_DIR );
	}
	$tmp = STATE_FILE . '.tmp';
	if ( file_put_contents( $tmp, json_encode( $doc, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ) . "\n" ) === false
			|| ! rename( $tmp, STATE_FILE ) ) {
		fail( 'cannot write ' . STATE_FILE );
	}
}

/** Directly attached IPv4 subnets (from the routing table, minus the default route). */
function local_subnets(): array {
	$out = [];
	foreach ( array_slice( (array) @file( '/proc/net/route', FILE_IGNORE_NEW_LINES ), 1 ) as $line ) {
		$f = preg_split( '/\s+/', trim( $line ) );
		if ( count( $f ) < 8 || $f[0] === 'lo' || $f[1] === '00000000' || $f[2] !== '00000000' ) {
			continue;
		}
		$net = long2ip( unpack( 'V', pack( 'H*', $f[1] ) )[1] );
		$bits = substr_count( decbin( unpack( 'V', pack( 'H*', $f[7] ) )[1] ), '1' );
		$out[] = "$net/$bits";
	}
	sort( $out );
	return array_values( array_unique( $out ) );
}

/** Names of the Docker networks this container is on: Docker's DNS answers a
 * PTR query for each of our addresses with "<container>.<network>". */
function networks(): array {
	static $nets = null;
	if ( $nets !== null ) {
		return $nets;
	}
	$nets = [];
	foreach ( preg_split( '/\s+/', trim( run( [ 'hostname', '-I' ] )[1] ) ) as $ip ) {
		if ( ! filter_var( $ip, FILTER_VALIDATE_IP, FILTER_FLAG_IPV4 ) ) {
			continue;
		}
		$ptr = implode( '.', array_reverse( explode( '.', $ip ) ) ) . '.in-addr.arpa';
		foreach ( @dns_get_record( $ptr, DNS_PTR ) ?: [] as $rec ) {
			$dot = strpos( $rec['target'] ?? '', '.' );
			if ( $dot !== false ) {
				$nets[] = substr( $rec['target'], $dot + 1 );
			}
		}
	}
	return $nets = array_values( array_unique( $nets ) );
}

/** Every IPv4 address of a container name. A plain lookup answers with its
 * address on ONE shared network only, while it may connect from any of them
 * (db-proxy layer: the edge and production share three), so the name is also
 * asked per network as "<name>.<network>". */
function resolve_name( string $name ): array {
	$ips = gethostbynamel( $name ) ?: [];
	if ( strpos( $name, '.' ) === false ) {
		foreach ( networks() as $net ) {
			$ips = array_merge( $ips, gethostbynamel( "$name.$net" ) ?: [] );
		}
	}
	$ips = array_values( array_unique( $ips ) );
	sort( $ips );
	return $ips;
}

/** Peer => list of source/destination specs ([] = unresolved; ['*'] = anywhere). */
function resolve( array $doc ): array {
	$out = [];
	foreach ( [ 'inbound', 'outbound' ] as $dir ) {
		foreach ( $doc[ $dir ] as $r ) {
			$peer = $r['peer'];
			if ( isset( $out[ $peer ] ) ) {
				continue;
			}
			if ( $peer === 'any' || $peer === 'internet' ) {
				$out[ $peer ] = [ '*' ];
			} elseif ( $peer === 'local-subnets' ) {
				$out[ $peer ] = local_subnets();
			} elseif ( valid_cidr( $peer ) ) {
				$out[ $peer ] = [ $peer ];
			} else {
				$out[ $peer ] = resolve_name( $peer );
			}
		}
	}
	ksort( $out );
	return $out;
}

function active( array $r ): bool {
	return $r['enabled'] && ( ! isset( $r['layer'] ) || $r['layer'] === layer() );
}

/** The iptables-restore input for the filter table. */
function render( array $doc, array $resolved ): string {
	$l = [ '*filter', ':PFW_IN - [0:0]', ':PFW_OUT - [0:0]', ':PFW_INET - [0:0]',
		'-F PFW_IN', '-F PFW_OUT', '-F PFW_INET' ];
	if ( ! $doc['enabled'] ) {
		$l[] = '-A PFW_IN -m comment --comment pfw:disabled -j ACCEPT';
		$l[] = '-A PFW_OUT -m comment --comment pfw:disabled -j ACCEPT';
		$l[] = 'COMMIT';
		return implode( "\n", $l ) . "\n";
	}
	foreach ( NON_INTERNET as $net ) {
		$l[] = "-A PFW_INET -d $net -j RETURN";
	}
	$l[] = '-A PFW_INET -j ACCEPT';
	foreach ( [ 'in' => 'PFW_IN', 'out' => 'PFW_OUT' ] as $dir => $chain ) {
		$l[] = "-A $chain " . ( $dir === 'in' ? '-i' : '-o' ) . ' lo -j ACCEPT';
		$l[] = "-A $chain -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT";
		$l[] = "-A $chain -m conntrack --ctstate INVALID -j DROP";
		foreach ( $doc[ $dir === 'in' ? 'inbound' : 'outbound' ] as $r ) {
			if ( ! active( $r ) ) {
				continue;
			}
			$ports = parse_ports( $r['ports'] );
			$protos = $r['proto'] === 'tcp/udp' ? [ 'tcp', 'udp' ] : [ $r['proto'] ];
			$target = $r['peer'] === 'internet' ? 'PFW_INET' : 'ACCEPT';
			foreach ( $resolved[ $r['peer'] ] ?? [] as $addr ) {
				$match = $addr === '*' ? '' : ( $dir === 'in' ? " -s $addr" : " -d $addr" );
				foreach ( $protos as $p ) {
					$l[] = "-A $chain$match -p $p -m multiport --dports $ports -m conntrack --ctstate NEW"
						. " -m comment --comment pfw:$dir:{$r['id']} -j $target";
				}
			}
		}
		if ( $dir === 'in' ) {
			$l[] = '-A PFW_IN -m comment --comment pfw:in:default -j DROP';
		} else {
			$l[] = '-A PFW_OUT -p tcp -m comment --comment pfw:out:default -j REJECT --reject-with tcp-reset';
			$l[] = '-A PFW_OUT -m comment --comment pfw:out:default -j REJECT --reject-with icmp-port-unreachable';
		}
	}
	$l[] = 'COMMIT';
	return implode( "\n", $l ) . "\n";
}

/** Same idea for IPv6, best effort: the stack networks are IPv4, so only
 * loopback and established traffic pass when the firewall is on. */
function render6( bool $enabled ): string {
	$l = [ '*filter', ':PFW_IN - [0:0]', ':PFW_OUT - [0:0]', '-F PFW_IN', '-F PFW_OUT' ];
	if ( $enabled ) {
		$l[] = '-A PFW_IN -i lo -j ACCEPT';
		$l[] = '-A PFW_IN -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT';
		$l[] = '-A PFW_IN -j DROP';
		$l[] = '-A PFW_OUT -o lo -j ACCEPT';
		$l[] = '-A PFW_OUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT';
		$l[] = '-A PFW_OUT -j REJECT';
	} else {
		$l[] = '-A PFW_IN -j ACCEPT';
		$l[] = '-A PFW_OUT -j ACCEPT';
	}
	$l[] = 'COMMIT';
	return implode( "\n", $l ) . "\n";
}

function hook( string $bin ): bool {
	foreach ( [ 'INPUT' => 'PFW_IN', 'OUTPUT' => 'PFW_OUT' ] as $builtin => $chain ) {
		if ( run( [ $bin, '-w', '5', '-C', $builtin, '-j', $chain ] )[0] !== 0
				&& run( [ $bin, '-w', '5', '-I', $builtin, '1', '-j', $chain ] )[0] !== 0 ) {
			return false;
		}
	}
	return true;
}

/** Loads the chains, then hooks them; throws RuntimeException on failure (never the other way round: a hook into
 * an empty chain would be a no-op, a half-loaded chain could lock us out). */
function enforce( array $doc ): array {
	$resolved = resolve( $doc );
	[ $code, , $err ] = run( [ 'iptables-restore', '-w', '5', '--noflush' ], render( $doc, $resolved ) );
	if ( $code !== 0 ) {
		throw new RuntimeException( 'iptables-restore failed: ' . trim( $err ) );
	}
	if ( ! hook( 'iptables' ) ) {
		throw new RuntimeException( 'cannot hook PFW_IN / PFW_OUT into INPUT / OUTPUT' );
	}
	$v6 = run( [ 'ip6tables-restore', '-w', '5', '--noflush' ], render6( $doc['enabled'] ) )[0] === 0
		&& hook( 'ip6tables' );
	$runtime = [ 'applied_at' => gmdate( 'c' ), 'layer' => layer(), 'resolved' => $resolved,
		'fingerprint' => fingerprint( $doc ), 'ipv6' => $v6 ];
	@file_put_contents( RUNTIME_FILE, json_encode( $runtime, JSON_UNESCAPED_SLASHES ) . "\n" );
	return $runtime;
}

/** sha256 of the canonical document -- the dashboard computes the same to
 * tell whether what it has is what is enforced. */
function fingerprint( array $doc ): string {
	return hash( 'sha256', json_encode( canonical( $doc ), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) );
}

function canonical( $v ) {
	if ( is_array( $v ) ) {
		if ( $v && array_keys( $v ) !== range( 0, count( $v ) - 1 ) ) {
			ksort( $v );
		}
		return array_map( 'canonical', $v );
	}
	return $v;
}

/** Packet counters per rule id from the live chains. */
function counters(): array {
	[ $code, $out ] = run( [ 'iptables-save', '-c', '-t', 'filter' ] );
	$hooked = [ 'in' => false, 'out' => false ];
	$hits = [ 'in' => [], 'out' => [] ];
	if ( $code !== 0 ) {
		return [ null, $hits ];
	}
	foreach ( explode( "\n", $out ) as $line ) {
		if ( preg_match( '/^\[\d+:\d+\] -A (INPUT|OUTPUT) -j PFW_(IN|OUT)$/', $line, $m ) ) {
			$hooked[ strtolower( $m[2] ) ] = true;
		} elseif ( preg_match( '/^\[(\d+):(\d+)\] -A PFW_(?:IN|OUT) .*--comment "?pfw:(in|out):([a-z0-9-]+)"?/', $line, $m ) ) {
			$hits[ $m[3] ][ $m[4] ]['packets'] = ( $hits[ $m[3] ][ $m[4] ]['packets'] ?? 0 ) + (int) $m[1];
			$hits[ $m[3] ][ $m[4] ]['bytes'] = ( $hits[ $m[3] ][ $m[4] ]['bytes'] ?? 0 ) + (int) $m[2];
		}
	}
	return [ $hooked['in'] && $hooked['out'], $hits ];
}

// -- commands -------------------------------------------------------------------

$cmd = $argv[1] ?? '';
try {
switch ( $cmd ) {
	case 'boot':
		$doc = load_saved( $source );
		$rt = enforce( $doc );
		$missing = array_keys( array_filter( $rt['resolved'], fn( $ips ) => ! $ips ) );
		echo "production-firewall: $source ruleset applied (" . ( $doc['enabled'] ? 'enforcing' : 'disabled' ) . ')'
			. ( $missing ? '; unresolved: ' . implode( ', ', $missing ) : '' ) . "\n";
		break;

	case 'apply':
		if ( ( $argv[2] ?? '' ) !== '--b64' || ! isset( $argv[3] ) ) {
			fail( 'usage: production-firewall apply --b64 <base64 JSON>', 2 );
		}
		$doc = json_decode( (string) base64_decode( $argv[3], true ), true );
		$errors = validate( $doc );
		if ( $errors ) {
			fail( "invalid ruleset:\n  " . implode( "\n  ", $errors ) );
		}
		enforce( $doc );
		save( $doc );
		echo "applied\n";
		break;

	case 'status':
		$doc = load_saved( $source );
		[ $hooked, $hits ] = counters();
		$rt = json_decode( (string) @file_get_contents( RUNTIME_FILE ), true ) ?: [];
		echo json_encode( [
			'source' => $source,
			'layer' => layer(),
			'hooked' => $hooked,
			'document' => $doc,
			'fingerprint' => fingerprint( $doc ),
			'enforced_fingerprint' => $rt['fingerprint'] ?? null,
			'applied_at' => $rt['applied_at'] ?? null,
			'resolved' => $rt['resolved'] ?? (object) [],
			'ipv6' => $rt['ipv6'] ?? null,
			'counters' => $hits,
		], JSON_UNESCAPED_SLASHES ) . "\n";
		break;

	case 'watch':
		while ( true ) {
			sleep( WATCH_INTERVAL );
			$doc = load_saved();
			$rt = json_decode( (string) @file_get_contents( RUNTIME_FILE ), true ) ?: [];
			if ( resolve( $doc ) == ( $rt['resolved'] ?? null ) && counters()[0] ) {
				continue;
			}
			try {
				enforce( $doc );
				echo 'production-firewall: peers changed or hook missing, ruleset re-applied at ' . gmdate( 'c' ) . "\n";
			} catch ( RuntimeException $e ) {
				fwrite( STDERR, 'production-firewall: re-apply failed: ' . $e->getMessage() . "\n" );
			}
		}

	case 'default':
		echo json_encode( load_default(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES ) . "\n";
		break;

	default:
		fail( 'usage: production-firewall boot|apply --b64 <doc>|status|watch|default', 2 );
}
} catch ( RuntimeException $e ) {
	fail( $e->getMessage() );
}
