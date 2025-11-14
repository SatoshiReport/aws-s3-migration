#!/usr/bin/env python3
"""Verify iwannabenewyork domain DNS and certificate configuration."""

import datetime
import socket
import ssl
import subprocess
import sys

import requests

try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from botocore.exceptions import ClientError

from cost_toolkit.scripts.setup.exceptions import CertificateInfoError

# HTTP status codes
HTTP_STATUS_MOVED_PERMANENTLY = 301
HTTP_STATUS_OK = 200

# Certificate tuple structure indices
CERT_TUPLE_MIN_LENGTH = 2

# Test success thresholds
MIN_TESTS_FOR_MOSTLY_WORKING = 4


def verify_dns_resolution(domain):
    """Test DNS resolution for the domain"""
    print(f"🔍 Testing DNS resolution for {domain}")

    try:
        # Test A record resolution
        ip_address = socket.gethostbyname(domain)
        print(f"  ✅ {domain} resolves to: {ip_address}")

        # Test www subdomain
        www_domain = f"www.{domain}"
        www_ip = socket.gethostbyname(www_domain)
        print(f"  ✅ {www_domain} resolves to: {www_ip}")

    except socket.gaierror as e:
        print(f"  ❌ DNS resolution failed: {e}")
        return False, None

    return True, ip_address


def verify_http_connectivity(domain):
    """Test HTTP connectivity and redirects"""
    print(f"\n🌐 Testing HTTP connectivity for {domain}")

    try:
        # Test HTTP (should redirect to HTTPS)
        http_url = f"http://{domain}"
        response = requests.get(http_url, allow_redirects=False, timeout=10)

        if (
            response.status_code == HTTP_STATUS_MOVED_PERMANENTLY
            and "https://" in response.headers.get("Location", "")
        ):
            print(
                f"  ✅ HTTP redirects to HTTPS ({HTTP_STATUS_MOVED_PERMANENTLY}): "
                f"{response.headers['Location']}"
            )
        else:
            print(f"  ⚠️  HTTP response: {response.status_code}")

    except requests.RequestException as e:
        print(f"  ❌ HTTP test failed: {e}")
        return False

    return True


def verify_https_connectivity(domain):
    """Test HTTPS connectivity and SSL certificate"""
    print(f"\n🔒 Testing HTTPS connectivity for {domain}")

    try:
        # Test HTTPS connectivity
        https_url = f"https://{domain}"
        response = requests.get(https_url, timeout=10)

        if response.status_code == HTTP_STATUS_OK:
            print(f"  ✅ HTTPS connection successful ({HTTP_STATUS_OK})")
            print(f"  ✅ Content-Type: {response.headers.get('Content-Type', 'Unknown')}")

            # Check if it's served by Cloudflare (Canva uses Cloudflare)
            server = response.headers.get("Server", "")
            if "cloudflare" in server.lower():
                print("  ✅ Served by Cloudflare (Canva infrastructure)")

            return True

    except requests.RequestException as e:
        print(f"  ❌ HTTPS test failed: {e}")
        return False

    print(f"  ⚠️  HTTPS response: {response.status_code}")
    return False


def _extract_cert_dict(cert_items):
    """Extract dictionary from certificate tuple structure"""
    cert_dict = {}
    if cert_items:
        for item in cert_items:
            if len(item) >= 1 and len(item[0]) >= CERT_TUPLE_MIN_LENGTH:
                cert_dict[item[0][0]] = item[0][1]
    return cert_dict


def _parse_cert_dates(cert):
    """Parse certificate dates"""
    if not cert or "notBefore" not in cert or "notAfter" not in cert:
        raise CertificateInfoError()

    not_before = datetime.datetime.strptime(str(cert["notBefore"]), "%b %d %H:%M:%S %Y %Z")
    not_after = datetime.datetime.strptime(str(cert["notAfter"]), "%b %d %H:%M:%S %Y %Z")
    return not_before, not_after


def _print_cert_info(subject_dict, issuer_dict, not_before, not_after):
    """Print certificate information"""
    print(f"  ✅ Certificate Subject: {subject_dict.get('commonName', 'Unknown')}")
    print(f"  ✅ Certificate Issuer: {issuer_dict.get('organizationName', 'Unknown')}")
    print(f"  ✅ Valid From: {not_before.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  ✅ Valid Until: {not_after.strftime('%Y-%m-%d %H:%M:%S UTC')}")


def _check_cert_validity(not_before, not_after):
    """Check if certificate is currently valid"""
    now = datetime.datetime.utcnow()
    if not_before <= now <= not_after:
        days_until_expiry = (not_after - now).days
        print(f"  ✅ Certificate is valid ({days_until_expiry} days until expiry)")
        return True
    print("  ❌ Certificate is not valid for current date")
    return False


def check_ssl_certificate(domain):
    """Check SSL certificate details"""
    print(f"\n🛡️  Checking SSL certificate for {domain}")

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

                if cert is None:
                    print("  ❌ No certificate received")
                    return False

                subject_dict = _extract_cert_dict(cert.get("subject"))
                issuer_dict = _extract_cert_dict(cert.get("issuer"))
                not_before, not_after = _parse_cert_dates(cert)

                _print_cert_info(subject_dict, issuer_dict, not_before, not_after)
                return _check_cert_validity(not_before, not_after)

    except ClientError as e:
        print(f"  ❌ SSL certificate check failed: {e}")
        return False


def verify_canva_verification(domain):
    """Check if Canva domain verification is in place"""
    print(f"\n🎨 Checking Canva domain verification for {domain}")

    try:
        # Check for Canva verification TXT record
        result = subprocess.run(
            ["dig", "+short", f"_canva-domain-verify.{domain}", "TXT"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            txt_record = result.stdout.strip().replace('"', "")
            print(f"  ✅ Canva verification TXT record found: {txt_record}")
            return True

    except ClientError as e:
        print(f"  ❌ Canva verification check failed: {e}")
        return False

    print("  ❌ No Canva verification TXT record found")
    return False


def _find_hosted_zone_for_domain(route53, domain):
    """Find the Route53 hosted zone for a domain"""
    response = route53.list_hosted_zones()
    hosted_zones = response.get("HostedZones", [])

    for zone in hosted_zones:
        if zone["Name"] == f"{domain}.":
            return zone
    return None


def _print_nameservers(route53, zone_id, domain):
    """Print nameservers for the zone"""
    records_response = route53.list_resource_record_sets(HostedZoneId=zone_id)
    records = records_response.get("ResourceRecordSets", [])

    for record in records:
        if record.get("Type") == "NS" and record.get("Name") == f"{domain}.":
            nameservers = [rr.get("Value") for rr in record.get("ResourceRecords", [])]
            print("  ✅ Nameservers configured:")
            for ns in nameservers:
                print(f"    - {ns}")
            break


def check_route53_configuration(domain):
    """Check Route53 configuration"""
    print(f"\n☁️  Checking Route53 configuration for {domain}")

    if not BOTO3_AVAILABLE:
        print("  ⚠️  boto3 not available, skipping Route53 check")
        return True

    try:
        route53 = boto3.client("route53")

        target_zone = _find_hosted_zone_for_domain(route53, domain)

        if not target_zone:
            print(f"  ❌ No Route53 hosted zone found for {domain}")
            return False

        zone_id = target_zone["Id"].split("/")[-1]
        print(f"  ✅ Route53 hosted zone found: {zone_id}")

        _print_nameservers(route53, target_zone["Id"], domain)

    except ClientError as e:
        print(f"  ❌ Route53 check failed: {e}")
        return False

    return True


def _run_tests(domain):
    """Run all verification tests"""
    tests = [
        ("DNS Resolution", lambda: verify_dns_resolution(domain)),
        ("HTTP Connectivity", lambda: verify_http_connectivity(domain)),
        ("HTTPS Connectivity", lambda: verify_https_connectivity(domain)),
        ("SSL Certificate", lambda: check_ssl_certificate(domain)),
        ("Canva Verification", lambda: verify_canva_verification(domain)),
        ("Route53 Configuration", lambda: check_route53_configuration(domain)),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if test_name == "DNS Resolution":
                success, _ = test_func()
                results.append((test_name, success))
            else:
                success = test_func()
                results.append((test_name, success))
        except ClientError as e:
            print(f"  ❌ {test_name} failed with error: {e}")
            results.append((test_name, False))

    return results


def _print_summary(results, _domain):
    """Print verification summary"""
    print("\n" + "=" * 80)
    print("🎯 VERIFICATION SUMMARY")
    print("=" * 80)

    passed_tests = [name for name, success in results if success]
    failed_tests = [name for name, success in results if not success]

    print(f"✅ Passed tests: {len(passed_tests)}/{len(results)}")
    for test_name in passed_tests:
        print(f"  ✅ {test_name}")

    if failed_tests:
        print(f"\n❌ Failed tests: {len(failed_tests)}")
        for test_name in failed_tests:
            print(f"  ❌ {test_name}")

    return passed_tests, failed_tests


def _print_overall_status(domain, passed_tests, _failed_tests, total_tests):
    """Print overall verification status"""
    if len(passed_tests) == total_tests:
        print(f"\n🎉 SUCCESS: {domain} is fully configured and working!")
        print(f"🌐 Your Canva website is accessible at: https://{domain}")
        print("🔒 SSL certificate is valid and secure")
        print("☁️  DNS is properly configured through Route53")
    elif len(passed_tests) >= MIN_TESTS_FOR_MOSTLY_WORKING:
        print(f"\n✅ MOSTLY WORKING: {domain} is functional with minor issues")
        print(f"🌐 Your Canva website should be accessible at: https://{domain}")
        print("⚠️  Some non-critical tests failed - check details above")
    else:
        print(f"\n❌ ISSUES DETECTED: {domain} has significant problems")
        print("🔧 Please review the failed tests and fix the issues")


def main():
    """Run domain verification tests and report results."""
    domain = "iwannabenewyork.com"

    print("🚀 Domain Verification for iwannabenewyork.com")
    print("=" * 80)
    print(f"Testing domain: {domain}")
    print("Target: Canva website")
    print(f"Timestamp: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)

    results = _run_tests(domain)
    passed_tests, failed_tests = _print_summary(results, domain)
    _print_overall_status(domain, passed_tests, failed_tests, len(results))

    print(f"\n💡 To run this verification again: python3 {__file__}")

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
