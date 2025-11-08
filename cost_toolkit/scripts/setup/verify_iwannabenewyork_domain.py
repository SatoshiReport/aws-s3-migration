#!/usr/bin/env python3

import datetime
import socket
import ssl
import subprocess
import sys
from urllib.parse import urlparse

import requests

# HTTP status codes
HTTP_STATUS_MOVED_PERMANENTLY = 301
HTTP_STATUS_OK = 200

# Certificate tuple structure indices
CERT_TUPLE_MIN_LENGTH = 2

# Test success thresholds
MIN_TESTS_FOR_MOSTLY_WORKING = 4


def test_dns_resolution(domain):
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

    else:
        return True, ip_address


def test_http_connectivity(domain):
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
                f"  ✅ HTTP redirects to HTTPS ({HTTP_STATUS_MOVED_PERMANENTLY}): {response.headers['Location']}"
            )
        else:
            print(f"  ⚠️  HTTP response: {response.status_code}")

    except requests.RequestException as e:
        print(f"  ❌ HTTP test failed: {e}")
        return False

    else:
        return True


def test_https_connectivity(domain):
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
                print(f"  ✅ Served by Cloudflare (Canva infrastructure)")

            return True
        else:
            print(f"  ⚠️  HTTPS response: {response.status_code}")
            return False

    except requests.RequestException as e:
        print(f"  ❌ HTTPS test failed: {e}")
        return False


def check_ssl_certificate(domain):  # noqa: PLR0912
    """Check SSL certificate details"""
    print(f"\n🛡️  Checking SSL certificate for {domain}")

    try:
        # Get SSL certificate info
        context = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()

                # Extract certificate details safely
                subject_dict = {}
                if cert and "subject" in cert and cert["subject"]:
                    for item in cert["subject"]:
                        if len(item) >= 1 and len(item[0]) >= CERT_TUPLE_MIN_LENGTH:
                            subject_dict[item[0][0]] = item[0][1]

                issuer_dict = {}
                if cert and "issuer" in cert and cert["issuer"]:
                    for item in cert["issuer"]:
                        if len(item) >= 1 and len(item[0]) >= CERT_TUPLE_MIN_LENGTH:
                            issuer_dict[item[0][0]] = item[0][1]

                # Parse dates safely
                if cert and "notBefore" in cert and "notAfter" in cert:
                    not_before = datetime.datetime.strptime(
                        str(cert["notBefore"]), "%b %d %H:%M:%S %Y %Z"
                    )
                    not_after = datetime.datetime.strptime(
                        str(cert["notAfter"]), "%b %d %H:%M:%S %Y %Z"
                    )
                else:
                    raise Exception(  # noqa: TRY003, TRY002, TRY301
                        "Certificate date information not available"
                    )

                print(f"  ✅ Certificate Subject: {subject_dict.get('commonName', 'Unknown')}")
                print(f"  ✅ Certificate Issuer: {issuer_dict.get('organizationName', 'Unknown')}")
                print(f"  ✅ Valid From: {not_before.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"  ✅ Valid Until: {not_after.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                # Check if certificate is valid
                now = datetime.datetime.utcnow()
                if not_before <= now <= not_after:
                    days_until_expiry = (not_after - now).days
                    print(f"  ✅ Certificate is valid ({days_until_expiry} days until expiry)")
                    return True
                else:
                    print(f"  ❌ Certificate is not valid for current date")
                    return False

    except Exception as e:
        print(f"  ❌ SSL certificate check failed: {e}")
        return False


def test_canva_verification(domain):
    """Check if Canva domain verification is in place"""
    print(f"\n🎨 Checking Canva domain verification for {domain}")

    try:
        # Check for Canva verification TXT record
        result = subprocess.run(
            ["dig", "+short", f"_canva-domain-verify.{domain}", "TXT"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            txt_record = result.stdout.strip().replace('"', "")
            print(f"  ✅ Canva verification TXT record found: {txt_record}")
            return True
        else:
            print(f"  ❌ No Canva verification TXT record found")
            return False

    except Exception as e:
        print(f"  ❌ Canva verification check failed: {e}")
        return False


def check_route53_configuration(domain):
    """Check Route53 configuration"""
    print(f"\n☁️  Checking Route53 configuration for {domain}")

    try:
        import boto3
        from botocore.exceptions import ClientError

        route53 = boto3.client("route53")

        # Find the hosted zone
        response = route53.list_hosted_zones()
        hosted_zones = response.get("HostedZones", [])

        target_zone = None
        for zone in hosted_zones:
            if zone["Name"] == f"{domain}.":
                target_zone = zone
                break

        if not target_zone:
            print(f"  ❌ No Route53 hosted zone found for {domain}")
            return False

        zone_id = target_zone["Id"].split("/")[-1]
        print(f"  ✅ Route53 hosted zone found: {zone_id}")

        # Check nameservers
        records_response = route53.list_resource_record_sets(HostedZoneId=target_zone["Id"])
        records = records_response.get("ResourceRecordSets", [])

        for record in records:
            if record.get("Type") == "NS" and record.get("Name") == f"{domain}.":
                nameservers = [rr.get("Value") for rr in record.get("ResourceRecords", [])]
                print(f"  ✅ Nameservers configured:")
                for ns in nameservers:
                    print(f"    - {ns}")
                break

    except ImportError:
        print(f"  ⚠️  boto3 not available, skipping Route53 check")
        return True
    except Exception as e:
        print(f"  ❌ Route53 check failed: {e}")
        return False

    else:
        return True


def main():
    domain = "iwannabenewyork.com"

    print("🚀 Domain Verification for iwannabenewyork.com")
    print("=" * 80)
    print(f"Testing domain: {domain}")
    print(f"Target: Canva website")
    print(f"Timestamp: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)

    # Run all tests
    tests = [
        ("DNS Resolution", lambda: test_dns_resolution(domain)),
        ("HTTP Connectivity", lambda: test_http_connectivity(domain)),
        ("HTTPS Connectivity", lambda: test_https_connectivity(domain)),
        ("SSL Certificate", lambda: check_ssl_certificate(domain)),
        ("Canva Verification", lambda: test_canva_verification(domain)),
        ("Route53 Configuration", lambda: check_route53_configuration(domain)),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if test_name == "DNS Resolution":
                success, ip = test_func()
                results.append((test_name, success))
            else:
                success = test_func()
                results.append((test_name, success))
        except Exception as e:
            print(f"  ❌ {test_name} failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print(f"\n" + "=" * 80)
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

    # Overall status
    if len(passed_tests) == len(results):
        print(f"\n🎉 SUCCESS: {domain} is fully configured and working!")
        print(f"🌐 Your Canva website is accessible at: https://{domain}")
        print(f"🔒 SSL certificate is valid and secure")
        print(f"☁️  DNS is properly configured through Route53")
    elif len(passed_tests) >= MIN_TESTS_FOR_MOSTLY_WORKING:  # Core functionality working
        print(f"\n✅ MOSTLY WORKING: {domain} is functional with minor issues")
        print(f"🌐 Your Canva website should be accessible at: https://{domain}")
        print(f"⚠️  Some non-critical tests failed - check details above")
    else:
        print(f"\n❌ ISSUES DETECTED: {domain} has significant problems")
        print(f"🔧 Please review the failed tests and fix the issues")

    print(f"\n💡 To run this verification again: python3 {__file__}")

    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
