"""Monitoring and summary utilities"""


def cleanup_ami_safe(ec2_client, ami_id):
    """Safely clean up AMI, ignoring errors."""
    try:
        ec2_client.deregister_image(ImageId=ami_id)
        print(f"   🧹 Cleaned up temporary AMI {ami_id}")
    except:
        pass


def _print_summary_header():
    """Print summary header."""
    print("\n" + "=" * 80)
    print("📊 EXPORT SUMMARY")
    print("=" * 80)


def _print_successful_exports(successful):
    """Print successful exports information."""
    if not successful:
        return

    total_savings = sum(r["monthly_savings"] for r in successful)
    print(f"💰 Total monthly savings: ${total_savings:.2f}")
    print(f"💰 Total annual savings: ${total_savings * 12:.2f}")

    print("\n📋 Successful Exports:")
    for result in successful:
        print(f"   {result['snapshot_id']} → s3://{result['bucket_name']}/{result['s3_key']}")


def _print_failed_exports(failed):
    """Print failed exports information."""
    if not failed:
        return

    print("\n❌ Failed Exports:")
    for result in failed:
        print(f"   {result['snapshot_id']}: {result.get('error', 'Unknown error')}")


def print_summary(results):
    """Print export summary."""
    _print_summary_header()

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"✅ Successful exports: {len(successful)}")
    print(f"❌ Failed exports: {len(failed)}")

    _print_successful_exports(successful)
    _print_failed_exports(failed)
