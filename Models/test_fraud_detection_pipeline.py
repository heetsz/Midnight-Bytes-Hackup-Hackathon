"""
test_fraud_detection_pipeline.py
═════════════════════════════════════════════════════════════════════════════

Complete test suite for the 4-phase fraud detection pipeline.
Tests both training and inference on synthetic and real data.

Usage:
  python test_fraud_detection_pipeline.py
  python test_fraud_detection_pipeline.py --phase PHASE_3
  python test_fraud_detection_pipeline.py --test-inference
  python test_fraud_detection_pipeline.py --test-batch

═════════════════════════════════════════════════════════════════════════════
"""

import sys
import json
import numpy as np
import pandas as pd
import torch
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Import pipeline components
try:
    from run_pipeline_phase_refactored import (
        PipelineConfig,
        Phase1Foundation, Phase2Context, Phase3Specialists, Phase4Synthesis,
        FraudDetectionInference, test_full_pipeline, demo_single_row_inference
    )
except ImportError as e:
    logger.error(f"Failed to import pipeline: {e}")
    sys.exit(1)


# ═════════════════════════════════════════════════════════════════════════════
# SYNTHETIC DATA GENERATION
# ═════════════════════════════════════════════════════════════════════════════

class SyntheticDataGenerator:
    """Generate synthetic transactions for testing."""
    
    @staticmethod
    def generate_legitimate_transactions(n: int = 1000) -> pd.DataFrame:
        """Generate n legitimate (non-fraud) transactions."""
        np.random.seed(42)
        
        transactions = []
        for i in range(n):
            txn = {
                "TransactionID": f"LEG_{i:06d}",
                "TransactionAmt": np.random.exponential(100) + 10,  # Typical amounts
                "card1": np.random.randint(1000, 10000),
                "card2": np.random.randint(100, 1000),
                "card3": np.random.randint(10, 100),
                "card4": np.random.choice([1, 2, 3, 4, 5]),
                "card5": np.random.randint(100, 1000),
                "card6": np.random.choice([100, 150, 200, 300, 400, 500]),
                "addr1": np.random.randint(1, 1000),
                "addr2": np.random.randint(1, 200),
                "P_emaildomain": np.random.choice(["gmail.com", "yahoo.com", "outlook.com"]),
                "isFraud": 0,
                # Device fields
                "device_novelty": np.random.beta(2, 5),  # Low novelty
                "device_match_ord": np.random.randint(1, 100),  # Known devices
                "id_31": np.random.randint(0, 200),
                "id_33": np.random.randint(0, 200),
                "DeviceType": np.random.choice([1, 2, 3]),
                # Time fields
                "delta_t": np.random.exponential(10000) + 1000,  # Typical delays
                # V-features (velocity/heuristics)
                **{f"V{j}": np.random.randn() for j in range(1, 50)},
                # C-features (categorical)
                **{f"C{j}": np.random.randint(0, 10) for j in range(1, 15)},
                # D-features (time/date)
                **{f"D{j}": np.random.randint(0, 100) for j in range(1, 16)},
            }
            transactions.append(txn)
        
        return pd.DataFrame(transactions)
    
    @staticmethod
    def generate_fraudulent_transactions(n: int = 100) -> pd.DataFrame:
        """Generate n fraudulent transactions with various fraud patterns."""
        np.random.seed(42)
        
        transactions = []
        fraud_patterns = ["new_device", "high_velocity", "unusual_amount", "combined"]
        
        for i in range(n):
            pattern = fraud_patterns[i % len(fraud_patterns)]
            
            if pattern == "new_device":
                txn = {
                    "TransactionID": f"FRAUD_{i:06d}",
                    "TransactionAmt": np.random.exponential(50) + 20,
                    "device_novelty": np.random.beta(5, 2),  # High novelty
                    "device_match_ord": 0,  # Never seen before
                    "delta_t": np.random.randint(100, 3600),  # Soon after login
                }
            elif pattern == "high_velocity":
                txn = {
                    "TransactionID": f"FRAUD_{i:06d}",
                    "TransactionAmt": np.random.exponential(200) + 50,
                    "device_novelty": np.random.beta(2, 5),
                    "device_match_ord": np.random.randint(1, 50),
                    "delta_t": np.random.randint(60, 300),  # Very close together
                }
            elif pattern == "unusual_amount":
                txn = {
                    "TransactionID": f"FRAUD_{i:06d}",
                    "TransactionAmt": np.random.exponential(500) + 2000,  # Unusually large
                    "device_novelty": np.random.beta(2, 5),
                    "device_match_ord": np.random.randint(1, 50),
                    "delta_t": np.random.exponential(5000) + 1000,
                }
            else:  # combined
                txn = {
                    "TransactionID": f"FRAUD_{i:06d}",
                    "TransactionAmt": np.random.exponential(300) + 1000,
                    "device_novelty": 0.9,
                    "device_match_ord": 0,
                    "delta_t": np.random.randint(100, 1000),
                }
            
            # Common fields
            txn.update({
                "card1": np.random.randint(1000, 10000),
                "card2": np.random.randint(100, 1000),
                "card3": np.random.randint(10, 100),
                "card4": np.random.choice([1, 2, 3, 4, 5]),
                "card5": np.random.randint(100, 1000),
                "card6": np.random.choice([100, 150, 200, 300, 400, 500]),
                "addr1": np.random.randint(1, 1000),
                "addr2": np.random.randint(1, 200),
                "P_emaildomain": np.random.choice(["gmail.com", "yahoo.com", "outlook.com"]),
                "isFraud": 1,
                "id_31": np.random.randint(0, 200),
                "id_33": np.random.randint(0, 200),
                "DeviceType": np.random.choice([1, 2, 3]),
                **{f"V{j}": np.random.randn() for j in range(1, 50)},
                **{f"C{j}": np.random.randint(0, 10) for j in range(1, 15)},
                **{f"D{j}": np.random.randint(0, 100) for j in range(1, 16)},
            })
            
            transactions.append(txn)
        
        return pd.DataFrame(transactions)
    
    @staticmethod
    def generate_mixed_dataset(legitimate_count: int = 5000, fraudulent_count: int = 500) -> pd.DataFrame:
        """Generate a mixed dataset with balanced fraud/legit ratio."""
        legit_df = SyntheticDataGenerator.generate_legitimate_transactions(legitimate_count)
        fraud_df = SyntheticDataGenerator.generate_fraudulent_transactions(fraudulent_count)
        
        df = pd.concat([legit_df, fraud_df], ignore_index=True)
        df = df.sample(frac=1, random_state=42).reset_index(drop=True)
        
        logger.info(f"Generated {len(df):,} transactions ({fraudulent_count} fraud, {legitimate_count} legit)")
        logger.info(f"  Fraud rate: {(df['isFraud'].sum() / len(df) * 100):.2f}%")
        
        return df


# ═════════════════════════════════════════════════════════════════════════════
# PHASE-BY-PHASE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestPhase1Foundation:
    """Test Phase 1: TabNet and Siamese Device Encoder."""
    
    @staticmethod
    def test_tabnet_training():
        """Test Model A: TabNet training and inference."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Phase 1 - TabNet Training")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        df = SyntheticDataGenerator.generate_mixed_dataset(1000, 100)
        
        phase1 = Phase1Foundation(cfg)
        df_with_embeddings = phase1.train_tabnet(df)
        
        assert "tabnet_embedding" in df_with_embeddings.columns, "Missing tabnet_embedding"
        assert "tabnet_logit" in df_with_embeddings.columns, "Missing tabnet_logit"
        assert df_with_embeddings["tabnet_embedding"].iloc[0].shape == (128,), "Wrong embedding dim"
        
        logger.info("✓ TabNet test passed")
        return df_with_embeddings
    
    @staticmethod
    def test_siamese_device_training():
        """Test Model B: Siamese Device Encoder training and inference."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Phase 1 - Siamese Device Encoder")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        df = SyntheticDataGenerator.generate_mixed_dataset(1000, 100)
        
        phase1 = Phase1Foundation(cfg)
        df_with_embeddings = phase1.train_siamese_device(df)
        
        assert "device_embedding" in df_with_embeddings.columns, "Missing device_embedding"
        assert df_with_embeddings["device_embedding"].iloc[0].shape == (64,), "Wrong embedding dim"
        
        logger.info("✓ Siamese Device Encoder test passed")
        return df_with_embeddings


class TestPhase2Context:
    """Test Phase 2: HeteroGNN and SeqTransformer."""
    
    @staticmethod
    def test_hetero_gnn():
        """Test Model E: HeteroGNN inference."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Phase 2 - HeteroGNN")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        df = SyntheticDataGenerator.generate_mixed_dataset(1000, 100)
        # Add Phase 1 embeddings (mock)
        df["tabnet_embedding"] = [np.random.randn(128) for _ in range(len(df))]
        df["tabnet_logit"] = np.random.rand(len(df))
        
        phase2 = Phase2Context(cfg)
        df_with_graph = phase2.train_hetero_gnn(df)
        
        assert "graph_embedding" in df_with_graph.columns, "Missing graph_embedding"
        assert "txn_graph_logit" in df_with_graph.columns, "Missing txn_graph_logit"
        assert "ring_score" in df_with_graph.columns, "Missing ring_score"
        
        logger.info("✓ HeteroGNN test passed")
        return df_with_graph
    
    @staticmethod
    def test_sequence_transformer():
        """Test Model C: Sequence Transformer inference."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Phase 2 - Sequence Transformer")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        df = SyntheticDataGenerator.generate_mixed_dataset(1000, 100)
        
        phase2 = Phase2Context(cfg)
        df_with_seq = phase2.train_sequence_transformer(df)
        
        assert "seq_embedding" in df_with_seq.columns, "Missing seq_embedding"
        assert "seq_anomaly_score" in df_with_seq.columns, "Missing seq_anomaly_score"
        assert "paysim_boost" in df_with_seq.columns, "Missing paysim_boost"
        
        logger.info("✓ Sequence Transformer test passed")
        return df_with_seq


class TestInference:
    """Test single-row inference."""
    
    @staticmethod
    def test_single_transaction_inference():
        """Test inference on a single transaction."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Single-Row Inference")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        inferrer = FraudDetectionInference(cfg)
        
        # High-risk transaction
        txn = {
            "TransactionID": "TXN_TEST_001",
            "TransactionAmt": 5000,
            "card1": 1234,
            "device_novelty": 0.9,
            "device_match_ord": 0,
            "delta_t": 300,
            "V1": 0.5,
            "C1": 1,
            "D1": 10,
        }
        
        result = inferrer.infer_single_row(txn, include_reasons=True)
        
        assert "TransactionID" in result, "Missing TransactionID"
        assert "raw_fraud_score" in result, "Missing raw_fraud_score"
        assert "calibrated_prob" in result, "Missing calibrated_prob"
        assert "decision" in result, "Missing decision"
        assert result["decision"] in ["approve", "mfa", "block"], "Invalid decision"
        assert "reasons" in result, "Missing reasons"
        
        logger.info(f"  Transaction: {txn['TransactionID']}")
        logger.info(f"  Amount: ${txn['TransactionAmt']:,.2f}")
        logger.info(f"  Device Novelty: {txn['device_novelty']:.2f}")
        logger.info(f"  Raw Score: {result['raw_fraud_score']:.4f}")
        logger.info(f"  Calibrated Prob: {result['calibrated_prob']:.4f}")
        logger.info(f"  Decision: {result['decision'].upper()}")
        logger.info(f"  Reasons: {result['reasons']}")
        
        logger.info("✓ Single-row inference test passed")
    
    @staticmethod
    def test_batch_inference():
        """Test batch inference on multiple transactions."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Batch Inference")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        inferrer = FraudDetectionInference(cfg)
        
        df = SyntheticDataGenerator.generate_mixed_dataset(100, 10)
        
        results = []
        for idx, row in df.head(50).iterrows():
            txn = row.to_dict()
            result = inferrer.infer_single_row(txn, include_reasons=False)
            results.append(result)
        
        results_df = pd.DataFrame(results)
        
        logger.info(f"  Processed {len(results_df)} transactions")
        logger.info(f"  Decision distribution:")
        logger.info(results_df["decision"].value_counts())
        logger.info(f"  Mean calibrated prob: {results_df['calibrated_prob'].mean():.4f}")
        logger.info(f"  Std calibrated prob: {results_df['calibrated_prob'].std():.4f}")
        
        logger.info("✓ Batch inference test passed")


class TestPipelineEnd2End:
    """End-to-end pipeline tests."""
    
    @staticmethod
    def test_full_pipeline():
        """Run complete 4-phase pipeline on synthetic data."""
        logger.info("\n" + "="*80)
        logger.info("TEST: Full Pipeline (4 Phases)")
        logger.info("="*80)
        
        cfg = PipelineConfig()
        cfg.ensure_dirs()
        
        # Generate data
        df = SyntheticDataGenerator.generate_mixed_dataset(2000, 200)
        
        # Phase 1
        logger.info("\n[1/4] Phase 1: Foundation...")
        phase1 = Phase1Foundation(cfg)
        df = phase1.run(df)
        assert "tabnet_logit" in df.columns
        logger.info("✓ Phase 1 complete")
        
        # Phase 2
        logger.info("\n[2/4] Phase 2: Context...")
        phase2 = Phase2Context(cfg)
        df = phase2.run(df)
        assert "txn_graph_logit" in df.columns
        logger.info("✓ Phase 2 complete")
        
        # Phase 3
        logger.info("\n[3/4] Phase 3: Specialists...")
        phase3 = Phase3Specialists(cfg)
        df = phase3.run(df)
        assert "synth_id_prob" in df.columns
        assert "ato_prob" in df.columns
        logger.info("✓ Phase 3 complete")
        
        # Phase 4
        logger.info("\n[4/4] Phase 4: Synthesis...")
        phase4 = Phase4Synthesis(cfg)
        df = phase4.run(df)
        assert "calibrated_prob" in df.columns
        assert "decision" in df.columns
        logger.info("✓ Phase 4 complete")
        
        # Evaluate
        test_full_pipeline(df, cfg)
        
        logger.info("\n✓ Full pipeline test passed")


# ═════════════════════════════════════════════════════════════════════════════
# TEST RUNNER
# ═════════════════════════════════════════════════════════════════════════════

def run_all_tests(test_filter: str = None):
    """Run all tests, optionally filtered by name."""
    logger.info("\n" + "="*80)
    logger.info("FRAUD DETECTION PIPELINE — COMPREHENSIVE TEST SUITE")
    logger.info("="*80)
    
    test_classes = [
        TestPhase1Foundation,
        TestPhase2Context,
        TestInference,
        TestPipelineEnd2End,
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        for method_name in dir(test_class):
            if method_name.startswith("test_"):
                if test_filter and test_filter.lower() not in method_name.lower():
                    continue
                
                total_tests += 1
                try:
                    method = getattr(test_class, method_name)
                    method()
                    passed_tests += 1
                except Exception as e:
                    failed_tests.append((method_name, str(e)))
                    logger.error(f"✗ {method_name} FAILED: {e}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    logger.info(f"Total:  {total_tests}")
    logger.info(f"Passed: {passed_tests}")
    logger.info(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        logger.info("\nFailed tests:")
        for test_name, error in failed_tests:
            logger.error(f"  • {test_name}: {error}")
    
    return len(failed_tests) == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test fraud detection pipeline")
    parser.add_argument("--test", type=str, default=None, help="Filter tests by name")
    parser.add_argument("--test-inference", action="store_true", help="Only test inference")
    parser.add_argument("--test-batch", action="store_true", help="Only test batch inference")
    parser.add_argument("--test-full", action="store_true", help="Only test full pipeline")
    
    args = parser.parse_args()
    
    if args.test_inference:
        TestInference.test_single_transaction_inference()
    elif args.test_batch:
        TestInference.test_batch_inference()
    elif args.test_full:
        TestPipelineEnd2End.test_full_pipeline()
    else:
        success = run_all_tests(args.test)
        sys.exit(0 if success else 1)
