"""
Test script to validate all imports in the restructured codebase
"""

import sys
import traceback

def test_tribernachi_imports():
    """Test Tribernachi module imports"""
    print("\n=== Testing Tribernachi Imports ===")
    try:
        from tribernachi.constants import V_T, PHI, GAMMA, BETA, EPSILON, ZETA, T_HEX_ALPHABET
        print(f"  ✓ Constants imported: V_T={V_T}, PHI={PHI}")

        from tribernachi.tensor_recurrence import TensorRecurrence
        print(f"  ✓ TensorRecurrence imported")

        from tribernachi.tvc_versioning import generate_tvc, int_to_base20
        print(f"  ✓ TVC Versioning imported")

        from tribernachi.tgc_encoder import TGCEncoder
        print(f"  ✓ TGCEncoder imported")

        # Quick functional test
        encoder = TGCEncoder()
        test_data = [1.0, 2.0, 3.0, 4.0, 5.0]
        compressed = encoder.compress_data(test_data)
        decompressed = encoder.decompress_data(compressed)
        print(f"  ✓ TGC compression/decompression works")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False

def test_features_imports():
    """Test Features module imports"""
    print("\n=== Testing Features Imports ===")
    try:
        from features.features_tf import compute_tf_mod, compute_tf_crit
        print(f"  ✓ TF features imported")

        from features.features_phi import compute_phi_sigma
        print(f"  ✓ Phi Sigma imported")

        from features.features_tvi import compute_tvi_enhanced
        print(f"  ✓ TVI Enhanced imported")

        from features.features_svc import compute_svc_delta
        print(f"  ✓ SVC Delta imported")

        from features.score_da_tem_e import compute_da_tem_e_minute
        print(f"  ✓ DA-TEM-E Score imported")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False

def test_cache_imports():
    """Test Cache module imports"""
    print("\n=== Testing Cache Imports ===")
    try:
        from cache.feature_cache_wrapper import FeatureCacheWrapper
        print(f"  ✓ FeatureCacheWrapper imported")

        # Quick functional test
        cache = FeatureCacheWrapper(cache_dir="./test_cache", enable_compression=True)
        print(f"  ✓ Cache wrapper initialized")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False

def test_orchestration_imports():
    """Test Orchestration module imports"""
    print("\n=== Testing Orchestration Imports ===")
    try:
        from orchestration.pipeline_orchestrator import PipelineOrchestrator
        print(f"  ✓ PipelineOrchestrator imported")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all import tests"""
    print("=" * 60)
    print("IMPORT TEST SUITE")
    print("=" * 60)

    results = {
        "Tribernachi": test_tribernachi_imports(),
        "Features": test_features_imports(),
        "Cache": test_cache_imports(),
        "Orchestration": test_orchestration_imports()
    }

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    for module, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{module:20s}: {status}")

    all_passed = all(results.values())
    print("=" * 60)
    if all_passed:
        print("ALL TESTS PASSED ✓")
    else:
        print("SOME TESTS FAILED ✗")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
