"""Read-only model API connectivity diagnostics. Never prints API keys.
Place in the project root beside .env, then: python diagnose_connection.py
Uses GET /models, not a chat generation request; does not change configuration.
"""
import argparse
import errno
import json
import os
import platform
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

KEYS = ('MODEL_BASE_URL', 'MODEL_NAME', 'MODEL_API_KEY', 'MODEL_TIMEOUT')


def read_config(path):
    values = {}
    if path.exists():
        for n, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                raise ValueError('Invalid .env format on line ' + str(n))
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip()
            if key not in KEYS:
                continue
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except ValueError:
                    raise ValueError('Invalid quoted .env value on line ' + str(n)) from None
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if not isinstance(value, str):
                raise ValueError('.env values must be text')
            values[key] = value
    sources = {}
    for key in KEYS:
        if key in os.environ:
            values[key] = os.environ[key]
            sources[key] = 'environment'
        elif key in values:
            sources[key] = '.env'
        else:
            sources[key] = 'unset'
    return values, sources


def classify_error(exc):
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    # Inspect locally; raw exception text may contain private URLs, so never print it.
    message = str(reason).lower()
    if isinstance(reason, ssl.SSLCertVerificationError) or 'certificate_verify_failed' in message:
        return 'tls_certificate_error', 'Check Python certificate trust, system clock, and HTTPS-inspecting proxies.'
    if isinstance(reason, socket.gaierror) or 'getaddrinfo' in message or 'name or service not known' in message:
        return 'dns_error', 'Host name resolution failed; check network and DNS.'
    if isinstance(reason, (TimeoutError, socket.timeout)) or 'timed out' in message:
        return 'timeout', 'Connection or response timed out; check network or proxy reachability.'
    if 'tunnel connection failed' in message:
        return 'proxy_tunnel_error', 'The configured proxy could not establish an HTTPS tunnel.'
    if isinstance(reason, ssl.SSLError) or any(s in message for s in ('wrong_version_number', 'unexpected_eof', 'ssl:')):
        return 'tls_handshake_error', 'TLS negotiation failed; inspect proxy protocol and network middleware.'
    if (isinstance(reason, ConnectionRefusedError) or getattr(reason, 'winerror', None) == 10061
            or getattr(reason, 'errno', None) == errno.ECONNREFUSED):
        return 'connection_refused', 'Destination or proxy refused the connection; check whether the configured proxy is running.'
    if isinstance(reason, ConnectionResetError) or getattr(reason, 'winerror', None) == 10054:
        return 'connection_reset', 'The remote host or network middleware reset the connection.'
    return 'network_error', 'Connection failed; use the error type/code and route comparison to investigate.'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def probe(base, key, selected_model, direct=False, timeout=12):
    handlers = [NoRedirect()]
    if direct:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(base.rstrip('/') + '/models',
          headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})
    started = time.monotonic()
    result = {'route': 'direct_for_this_request_only' if direct else 'same_proxy_detection_as_project'}
    try:
        with opener.open(req, timeout=timeout) as response:
            result['http_status'] = response.status
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            result.update(status='unexpected_response', hint='Model list response exceeds diagnostic size limit.')
        else:
            try:
                payload = json.loads(raw)
                items = payload.get('data') if isinstance(payload, dict) else None
                if not isinstance(items, list):
                    raise ValueError('not a model list')
                ids = {m['id'] for m in items if isinstance(m, dict) and isinstance(m.get('id'), str)}
                result.update(status='connected', selected_model_in_list=selected_model in ids,
                              hint='Transport and model-list request succeeded. Chat generation still needs separate verification.')
            except (ValueError, TypeError):
                result.update(status='unexpected_response', hint='Endpoint returned HTTP success but not a model-list JSON object.')
    except urllib.error.HTTPError as exc:
        hints = {401:'API key rejected. Check its provider and validity.',403:'Request was forbidden; check account/network restrictions.',
                 404:'Model list endpoint not found. Check API base URL.',429:'Rate or account limit; check provider account status.'}
        result.update(status='http_error', http_status=exc.code,
                      hint=hints.get(exc.code, 'Server returned an HTTP error. No provider response body was printed.'))
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        kind, hint = classify_error(exc)
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        result.update(status='connection_error', kind=kind, reason_type=type(reason).__name__, hint=hint)
        for field in ('errno', 'winerror'):
            value = getattr(reason, field, None)
            if isinstance(value, int):
                result[field] = value
    result['duration_ms'] = round((time.monotonic()-started)*1000, 1)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', default='.env', help='Configuration file; defaults to .env in current directory')
    args = parser.parse_args(argv)
    try:
        values, sources = read_config(Path(args.env))
        base = values.get('MODEL_BASE_URL', '').rstrip('/')
        parsed = urlparse(base)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Use an HTTPS model API base URL with no credentials/query/fragment.')
        if not values.get('MODEL_API_KEY') or not values.get('MODEL_NAME'):
            raise ValueError('MODEL_API_KEY and MODEL_NAME must be configured.')
    except (OSError, ValueError):
        print(json.dumps({'status':'configuration_error', 'hint':'Place this script beside your project .env and run from that directory. Check .env formatting and required values.'}, indent=2))
        return 2
    proxies = urllib.request.getproxies()
    proxy_detected = any(proxies.get(k) for k in ('https', 'http', 'all'))
    report = {'python':platform.python_version(), 'api_base_url':base,
              'api_key_configured':True, 'config_sources':sources,
              'proxy_detected':proxy_detected,
              'note':'No credentials or raw exception text are printed. Configuration and certificate verification are unchanged.'}
    results = [probe(base,values['MODEL_API_KEY'],values['MODEL_NAME'])]
    # Only compare routing if a proxy is configured and the default route failed.
    # This does not alter system or environment proxy settings.
    if proxy_detected and results[0]['status'] != 'connected':
        results.append(probe(base,values['MODEL_API_KEY'],values['MODEL_NAME'],direct=True))
    report['checks'] = results
    print(json.dumps(report,ensure_ascii=True,indent=2))
    return 0 if any(r['status']=='connected' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
