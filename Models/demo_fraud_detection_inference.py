"""
demo_fraud_detection_inference.py
═════════════════════════════════════════════════════════════════════════════

Real-world fraud detection demonstration with various transaction scenarios.
This script shows practical usage of the 4-phase architecture for inference.

Usage:
  python demo_fraud_detection_inference.py                  # All scenarios
  python demo_fraud_detection_inference.py --scenario high_value
  python demo_fraud_detection_inference.py --scenario ato
  python demo_fraud_detection_inference.py --interactive

═════════════════════════════════════════════════════════════════════════════
"""

import json
import sys
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════

class TransactionScenarios:
    """Collection of realistic fraud detection scenarios."""
    
    @staticmethod
    def scenario_legitimate_purchase() -> Dict[str, Any]:
        """Normal, legitimate transaction."""
        return {
            "TransactionID": "TXN_LEG_001",
            "TransactionAmt": 85.50,  # Typical amount
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,  # Credit
            "card5": 165,
            "card6": 398,
            "addr1": 345,
            "addr2": 88,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.05,  # Well-known device
            "device_match_ord": 127,  # 127th use on this device
            "id_31": 15,
            "id_33": 45,
            "DeviceType": 1,  # Desktop
            "delta_t": 86400,  # 1 day since last transaction
            "V1": 0.1, "V2": 0.15, "C1": 1, "C2": 2, "D1": 5, "D2": 10,
        }
    
    @staticmethod
    def scenario_high_value_legitimate() -> Dict[str, Any]:
        """High-value but legitimate transaction."""
        return {
            "TransactionID": "TXN_LEG_002",
            "TransactionAmt": 4500.00,  # High but legitimate (jewelry/appliance)
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 345,
            "addr2": 88,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.05,  # Known device
            "device_match_ord": 127,
            "id_31": 15,
            "id_33": 45,
            "DeviceType": 1,
            "delta_t": 86400 * 7,  # Weekly purchase
            "V1": 0.3, "V2": 0.45, "C1": 5, "C2": 7, "D1": 12, "D2": 20,
        }
    
    @staticmethod
    def scenario_new_device_fraud() -> Dict[str, Any]:
        """Fraud red flag: New device + quick transaction after login."""
        return {
            "TransactionID": "TXN_FRAUD_001",
            "TransactionAmt": 2500.00,
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 345,
            "addr2": 88,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.95,  # NEW device (first time)
            "device_match_ord": 0,  # Never seen before
            "id_31": 200,  # Different device
            "id_33": 180,
            "DeviceType": 3,  # Mobile (unusual for this user)
            "delta_t": 180,  # 3 minutes after login (ATO signal)
            "V1": 0.8, "V2": 0.9, "C1": 8, "C2": 9, "D1": 50, "D2": 80,
        }
    
    @staticmethod
    def scenario_velocity_fraud() -> Dict[str, Any]:
        """Fraud pattern: Multiple high transactions in rapid succession."""
        return {
            "TransactionID": "TXN_FRAUD_002",
            "TransactionAmt": 3200.00,
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 345,
            "addr2": 88,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.1,  # Known device
            "device_match_ord": 50,
            "id_31": 15,
            "id_33": 45,
            "DeviceType": 1,
            "delta_t": 120,  # 2 minutes (5th transaction in 10 minutes!)
            "V1": 0.9, "V2": 0.95,  # High velocity metrics
            "C1": 9, "C2": 10, "D1": 90, "D2": 95,  # All maxed out
        }
    
    @staticmethod
    def scenario_unusual_location() -> Dict[str, Any]:
        """Fraud signal: Transaction from unusual geographic region."""
        return {
            "TransactionID": "TXN_FRAUD_003",
            "TransactionAmt": 1800.00,
            "card1": 4532,  # Usually US
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 998,  # Unusual (high address code = overseas)
            "addr2": 192,  # Doesn't match user's pattern
            "P_emaildomain": "yahoo.com",  # Changed from gmail
            "device_novelty": 0.85,  # Somewhat new device
            "device_match_ord": 5,  # Rarely used device
            "id_31": 180,
            "id_33": 170,
            "DeviceType": 2,  # Tablet (unusual)
            "delta_t": 600,  # Within 10 min
            "V1": 0.6, "V2": 0.7, "C1": 6, "C2": 8, "D1": 40, "D2": 60,
        }
    
    @staticmethod
    def scenario_third_party_fraud() -> Dict[str, Any]:
        """Fraud pattern: Small test transactions + credentials compromise."""
        return {
            "TransactionID": "TXN_FRAUD_004",
            "TransactionAmt": 1.99,  # Tiny amount (credential test)
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 500,
            "addr2": 100,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.9,  # New
            "device_match_ord": 0,  # First time
            "id_31": 199,
            "id_33": 198,
            "DeviceType": 2,
            "delta_t": 30,  # Immediately after login
            "V1": 0.05, "V2": 0.1,  # Anomalous feature pattern
            "C1": 2, "C2": 3, "D1": 15, "D2": 25,
        }
    
    @staticmethod
    def scenario_mfa_required() -> Dict[str, Any]:
        """Borderline case: Medium risk, warrants MFA."""
        return {
            "TransactionID": "TXN_MFA_001",
            "TransactionAmt": 750.00,
            "card1": 4532,
            "card2": 123,
            "card3": 25,
            "card4": 1,
            "card5": 165,
            "card6": 398,
            "addr1": 345,
            "addr2": 88,
            "P_emaildomain": "gmail.com",
            "device_novelty": 0.45,  # Somewhat new
            "device_match_ord": 15,  # Seen before but rare
            "id_31": 80,
            "id_33": 90,
            "DeviceType": 2,  # Mobile
            "delta_t": 2000,  # Few hours
            "V1": 0.4, "V2": 0.5, "C1": 4, "C2": 5, "D1": 30, "D2": 40,
        }


# ═════════════════════════════════════════════════════════════════════════════
# DEMONSTRATION ENGINE
# ═════════════════════════════════════════════════════════════════════════════

class FraudDetectionDemo:
    """Interactive fraud detection demonstration."""
    
    def __init__(self):
        self.cfg = PipelineConfig()
        self.inferrer = FraudDetectionInference(self.cfg)
        self.scenarios = TransactionScenarios()
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """Format inference result for display."""
        output = []
        output.append("\n" + "="*70)
        output.append(f"FRAUD DETECTION RESULT — {result['TransactionID']}")
        output.append("="*70)
        
        cal_prob = result['calibrated_prob']
        raw_score = result['raw_fraud_score']
        decision = result['decision'].upper()
        
        # Color-coded decision
        if decision == "APPROVE":
            decision_str = f"✓ APPROVE (Low Risk)"
            color = "🟢"
        elif decision == "MFA":
            decision_str = f"⚠ MFA REQUIRED (Medium Risk)"
            color = "🟡"
        else:  # BLOCK
            decision_str = f"✗ BLOCK (High Risk)"
            color = "🔴"
        
        output.append(f"\n{color} Decision: {decision_str}")
        output.append(f"  • Fraud Probability: {cal_prob:.2%}")
        output.append(f"  • Raw Score: {raw_score:.4f}")
        
        # Risk factors
        if result['reasons']:
            output.append(f"\n📊 Risk Factors:")
            for i, reason in enumerate(result['reasons'], 1):
                output.append(f"  {i}. {reason}")
        
        # Threshold explanation
        output.append(f"\n📏 Thresholds:")
        output.append(f"  • APPROVE:  < 30%")
        output.append(f"  • MFA:      30% - 70%")
        output.append(f"  • BLOCK:    > 70%")
        
        output.append(f"\n⏱️ Timestamp: {result['timestamp']}")
        output.append("="*70 + "\n")
        
        return "\n".join(output)
    
    def demo_scenario(self, scenario_name: str, scenario_func):
        """Demonstrate a single scenario."""
        logger.info(f"\n{'#'*70}")
        logger.info(f"SCENARIO: {scenario_name}")
        logger.info(f"{'#'*70}")
        
        # Get transaction
        txn = scenario_func()
        
        # Log transaction details
        logger.info(f"\nTransaction Details:")
        logger.info(f"  • Amount: ${txn['TransactionAmt']:,.2f}")
        logger.info(f"  • Device Novelty: {txn['device_novelty']:.2f}")
        logger.info(f"  • Device Match Order: {txn['device_match_ord']}")
        logger.info(f"  • Time Since Last Txn: {txn['delta_t']} seconds")
        logger.info(f"  • V-Features: V1={txn['V1']}, V2={txn['V2']}")
        
        # Infer
        logger.info(f"\nRunning inference...")
        result = self.inferrer.infer_single_row(txn, include_reasons=True)
        
        # Display result
        print(self.format_result(result))
        
        return result
    
    def run_all_scenarios(self):
        """Run all demonstration scenarios."""
        logger.info("\n" + "="*70)
        logger.info("FRAUD DETECTION PIPELINE DEMONSTRATION")
        logger.info("4-Phase Architecture: Foundation → Context → Specialists → Synthesis")
        logger.info("="*70)
        
        scenarios = [
            ("✓ Legitimate Online Purchase", self.scenarios.scenario_legitimate_purchase),
            ("✓ High-Value Legitimate Purchase", self.scenarios.scenario_high_value_legitimate),
            ("✗ New Device Fraud (ATO Pattern)", self.scenarios.scenario_new_device_fraud),
            ("✗ Velocity Fraud (Multiple Rapid Txns)", self.scenarios.scenario_velocity_fraud),
            ("✗ Unusual Location Fraud", self.scenarios.scenario_unusual_location),
            ("✗ Third-Party Fraud (Credential Test)", self.scenarios.scenario_third_party_fraud),
            ("⚠ MFA Required (Borderline)", self.scenarios.scenario_mfa_required),
        ]
        
        results = []
        for scenario_name, scenario_func in scenarios:
            result = self.demo_scenario(scenario_name, scenario_func)
            results.append({
                "scenario": scenario_name,
                "decision": result['decision'],
                "probability": result['calibrated_prob'],
            })
        
        # Summary
        self._print_summary(results)
    
    def _print_summary(self, results: List[Dict]):
        """Print summary of all scenarios."""
        logger.info("\n" + "="*70)
        logger.info("DEMONSTRATION SUMMARY")
        logger.info("="*70)
        
        df_results = pd.DataFrame(results)
        logger.info("\nDecision Distribution:")
        for decision in ["approve", "mfa", "block"]:
            count = (df_results['decision'] == decision).sum()
            pct = count / len(results) * 100
            logger.info(f"  • {decision.upper():10s}: {count:2d} ({pct:5.1f}%)")
        
        logger.info(f"\nFraud Probability Statistics:")
        logger.info(f"  • Mean:    {df_results['probability'].mean():.2%}")
        logger.info(f"  • Median:  {df_results['probability'].median():.2%}")
        logger.info(f"  • Min:     {df_results['probability'].min():.2%}")
        logger.info(f"  • Max:     {df_results['probability'].max():.2%}")
        logger.info(f"  • Std Dev: {df_results['probability'].std():.2%}")
        
        logger.info(f"\n{'Scenario':<40} {'Decision':<10} {'Probability':<12}")
        logger.info("-" * 70)
        for i, row in df_results.iterrows():
            logger.info(
                f"{row['scenario']:<40} "
                f"{row['decision'].upper():<10} "
                f"{row['probability']:.2%}"
            )
        
        logger.info("="*70)
    
    def interactive_mode(self):
        """Interactive mode for custom transactions."""
        logger.info("\n" + "="*70)
        logger.info("INTERACTIVE FRAUD DETECTION")
        logger.info("="*70)
        
        while True:
            logger.info("\nOptions:")
            logger.info("  1. Scenario: Legitimate Purchase")
            logger.info("  2. Scenario: New Device Fraud")
            logger.info("  3. Scenario: Velocity Fraud")
            logger.info("  4. Scenario: Unusual Location")
            logger.info("  5. Custom Transaction (JSON)")
            logger.info("  6. Exit")
            
            choice = input("\nSelect option (1-6): ").strip()
            
            if choice == "1":
                txn = self.scenarios.scenario_legitimate_purchase()
                self.demo_scenario("Legitimate Purchase", lambda: txn)
            elif choice == "2":
                txn = self.scenarios.scenario_new_device_fraud()
                self.demo_scenario("New Device Fraud", lambda: txn)
            elif choice == "3":
                txn = self.scenarios.scenario_velocity_fraud()
                self.demo_scenario("Velocity Fraud", lambda: txn)
            elif choice == "4":
                txn = self.scenarios.scenario_unusual_location()
                self.demo_scenario("Unusual Location", lambda: txn)
            elif choice == "5":
                try:
                    json_str = input("Enter transaction JSON: ")
                    txn = json.loads(json_str)
                    result = self.inferrer.infer_single_row(txn, include_reasons=True)
                    print(self.format_result(result))
                except json.JSONDecodeError:
                    logger.error("Invalid JSON format")
            elif choice == "6":
                logger.info("Exiting...")
                break
            else:
                logger.warning("Invalid option")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Fraud Detection Pipeline Demonstration"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=[
            "legitimate", "high_value", "new_device",
            "velocity", "unusual_location", "third_party", "mfa"
        ],
        help="Run specific scenario"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode"
    )
    
    args = parser.parse_args()
    
    demo = FraudDetectionDemo()
    
    if args.interactive:
        demo.interactive_mode()
    elif args.scenario:
        scenarios_map = {
            "legitimate": ("✓ Legitimate", demo.scenarios.scenario_legitimate_purchase),
            "high_value": ("✓ High-Value Legitimate", demo.scenarios.scenario_high_value_legitimate),
            "new_device": ("✗ New Device Fraud", demo.scenarios.scenario_new_device_fraud),
            "velocity": ("✗ Velocity Fraud", demo.scenarios.scenario_velocity_fraud),
            "unusual_location": ("✗ Unusual Location", demo.scenarios.scenario_unusual_location),
            "third_party": ("✗ Third-Party Fraud", demo.scenarios.scenario_third_party_fraud),
            "mfa": ("⚠ MFA Required", demo.scenarios.scenario_mfa_required),
        }
        name, func = scenarios_map[args.scenario]
        demo.demo_scenario(name, func)
    else:
        demo.run_all_scenarios()


if __name__ == "__main__":
    main()
