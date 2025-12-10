import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestGlobalOptimization(unittest.TestCase):
    def setUp(self):
        try:
            from blockchain_balance_fetcher import BlockchainBalanceFetcher
            self.fetcher = BlockchainBalanceFetcher()
        except ImportError:
            self.fail("Could not import BlockchainBalanceFetcher")

    def test_parallel_global_fetch(self):
        """Test that fetch_all_balances calls chain fetchers concurrently"""
        
        # Mock individual fetchers
        self.fetcher.fetch_bitcoin_balance = MagicMock(return_value=1.5)
        self.fetcher.fetch_ethereum_balance = MagicMock(return_value=10.0)
        self.fetcher.fetch_xrp_balance = MagicMock(return_value=500.0)
        self.fetcher.fetch_solana_balance = MagicMock(return_value=50.0)
        
        # Test config
        wallet_config = {
            "btc_address": "btc123",
            "eth_address": "eth123",
            "xrp_address": "xrp123",
            "sol_address": "sol123"
        }
        
        print("\nRunning global parallel fetch test...")
        balances = self.fetcher.fetch_all_balances(wallet_config, prompt_for_btc=False)
        
        # Verify results
        self.assertEqual(balances.get("BTC"), 1.5)
        self.assertEqual(balances.get("ETH"), 10.0)
        self.assertEqual(balances.get("XRP"), 500.0)
        self.assertEqual(balances.get("SOL"), 50.0)
        
        # Verify calls were made
        self.fetcher.fetch_bitcoin_balance.assert_called_once()
        self.fetcher.fetch_ethereum_balance.assert_called_once()
        self.fetcher.fetch_xrp_balance.assert_called_once()
        self.fetcher.fetch_solana_balance.assert_called_once()
        
        print("Global parallel fetch test passed!")

if __name__ == '__main__':
    unittest.main()
